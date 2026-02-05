import datetime
from abc import ABC, abstractmethod

from app.models.schemas import FormField, LookupItem, ResamplePeriod, TimeSeries


class DataAdapter(ABC):
    name: str
    description: str
    aggregation_method: str = "mean"

    @abstractmethod
    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries: ...

    def form_fields(self) -> list[FormField]:
        """Return form field definitions for this adapter's query UI.

        Override to provide adapter-specific fields (dropdowns, autocomplete).
        Default returns a single text field.
        """
        return [
            FormField(
                name="query",
                label="Query",
                field_type="text",
                placeholder="Enter query...",
            )
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Return lookup items for autocomplete fields.

        Override to provide dynamic options (e.g. team lists, player lists).
        """
        return []

    def custom_resample_periods(self) -> list[ResamplePeriod]:
        """Return custom resample periods this adapter supports.

        Override to provide domain-specific time periods (e.g. sports seasons).
        Default returns empty list (only standard periods available).
        """
        return []

    def custom_resample(self, series: TimeSeries, period: str) -> TimeSeries:
        """Apply custom resampling to a time series.

        Override to implement adapter-specific resampling logic.
        Only called for periods returned by custom_resample_periods().

        Args:
            series: Input time series.
            period: Custom period identifier (e.g. "mls_season").

        Returns:
            Resampled TimeSeries.
        """
        raise NotImplementedError(
            f"Adapter '{self.name}' does not support custom resample period '{period}'"
        )
