import csv
import datetime
import io
import uuid
from dataclasses import dataclass

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, LookupItem, TimeSeries

# In-memory storage for uploaded CSVs
_uploads: dict[str, "UploadedCSV"] = {}


@dataclass
class UploadedCSV:
    upload_id: str
    name: str
    series: TimeSeries
    created_at: datetime.datetime


def parse_csv_content(content: str, name: str) -> TimeSeries:
    """Parse CSV content and auto-detect date/value columns."""
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    if len(rows) < 2:
        raise ValueError("CSV must have at least a header row and one data row")

    header = [col.lower().strip() for col in rows[0]]

    # Try to find date column
    date_col_idx = None
    date_candidates = ["date", "time", "timestamp", "day", "datetime", "dt"]
    for i, col in enumerate(header):
        if any(cand in col for cand in date_candidates):
            date_col_idx = i
            break

    # If not found, assume first column is date
    if date_col_idx is None:
        date_col_idx = 0

    # Try to find value column
    value_col_idx = None
    value_candidates = [
        "value", "count", "amount", "total", "downloads", "price", "metric"
    ]
    for i, col in enumerate(header):
        if i != date_col_idx and any(cand in col for cand in value_candidates):
            value_col_idx = i
            break

    # If not found, assume second column is value
    if value_col_idx is None:
        value_col_idx = 1 if date_col_idx != 1 else 0
        if value_col_idx == date_col_idx:
            value_col_idx = (date_col_idx + 1) % len(header)

    if value_col_idx >= len(header):
        raise ValueError("Could not determine value column")

    # Parse data rows
    points: list[DataPoint] = []
    date_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%m-%d-%Y",
        "%d-%m-%Y",
    ]

    for row_idx, row in enumerate(rows[1:], start=2):
        if len(row) <= max(date_col_idx, value_col_idx):
            continue  # Skip incomplete rows

        date_str = row[date_col_idx].strip()
        value_str = row[value_col_idx].strip()

        # Parse date
        parsed_date = None
        for fmt in date_formats:
            try:
                parsed_date = datetime.datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue

        if parsed_date is None:
            raise ValueError(f"Could not parse date '{date_str}' in row {row_idx}")

        # Parse value
        try:
            value = float(value_str.replace(",", ""))
        except ValueError:
            raise ValueError(f"Could not parse value '{value_str}' in row {row_idx}")

        points.append(DataPoint(date=parsed_date, value=value))

    if not points:
        raise ValueError("No valid data points found in CSV")

    # Sort by date
    points.sort(key=lambda p: p.date)

    return TimeSeries(
        source="csv",
        query=name,
        points=points,
        metadata={"name": name, "uploaded": True},
    )


def store_upload(name: str, series: TimeSeries) -> str:
    """Store an uploaded CSV and return its upload ID."""
    upload_id = str(uuid.uuid4())[:8]
    _uploads[upload_id] = UploadedCSV(
        upload_id=upload_id,
        name=name,
        series=series,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
    )
    return upload_id


def get_upload(upload_id: str) -> UploadedCSV | None:
    """Get an uploaded CSV by ID."""
    return _uploads.get(upload_id)


def list_uploads() -> list[UploadedCSV]:
    """List all uploaded CSVs."""
    return sorted(_uploads.values(), key=lambda u: u.created_at, reverse=True)


def delete_upload(upload_id: str) -> bool:
    """Delete an uploaded CSV by ID."""
    if upload_id in _uploads:
        del _uploads[upload_id]
        return True
    return False


class CSVUploadAdapter(DataAdapter):
    name = "csv"
    description = "Custom CSV uploads (date/value columns)"
    aggregation_method = "mean"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="query",
                label="Uploaded Dataset",
                field_type="autocomplete",
                placeholder="Select uploaded CSV...",
                depends_on=None,
            )
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Return list of uploaded CSVs for autocomplete."""
        if lookup_type == "query":
            uploads = list_uploads()
            return [
                LookupItem(value=u.upload_id, label=u.name)
                for u in uploads
            ]
        return []

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        upload = get_upload(query)
        if upload is None:
            raise ValueError(f"Upload '{query}' not found. Please upload a CSV first.")

        # Clone the series and apply date filters
        points = upload.series.points

        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata=upload.series.metadata,
        )
