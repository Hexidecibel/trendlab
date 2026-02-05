import datetime

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, FormField, FormFieldOption, TimeSeries

REDDIT_API_URL = "https://www.reddit.com/r/{subreddit}/about.json"


class RedditAdapter(DataAdapter):
    name = "reddit"
    description = "Reddit subreddit metrics (current snapshot)"
    aggregation_method = "last"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="subreddit",
                label="Subreddit",
                field_type="text",
                placeholder="python",
            ),
            FormField(
                name="metric",
                label="Metric",
                field_type="select",
                options=[
                    FormFieldOption(value="subscribers", label="Subscribers"),
                    FormFieldOption(value="active_users", label="Active Users"),
                ],
            ),
        ]

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        # Parse query: subreddit:metric
        parts = query.split(":")
        if len(parts) != 2:
            raise ValueError("Query must be in format 'subreddit:metric'")

        subreddit = parts[0].strip().lower()
        metric = parts[1].strip().lower()

        if subreddit.startswith("r/"):
            subreddit = subreddit[2:]

        url = REDDIT_API_URL.format(subreddit=subreddit)

        headers = {
            "User-Agent": "TrendLab/1.0 (trend analysis bot)",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=30)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(f"Subreddit 'r/{subreddit}' not found") from None
                if response.status_code == 403:
                    msg = f"Subreddit 'r/{subreddit}' is private or banned"
                    raise ValueError(msg) from None
                raise

        data = response.json().get("data", {})

        # Extract the requested metric
        if metric == "subscribers":
            value = float(data.get("subscribers", 0))
            metric_label = "Subscribers"
        elif metric == "active_users":
            active = data.get("accounts_active", 0) or data.get("active_user_count", 0)
            value = float(active)
            metric_label = "Active Users"
        else:
            raise ValueError(
                f"Unknown metric '{metric}'. Use 'subscribers' or 'active_users'"
            )

        # Reddit API only provides current snapshot, not historical data
        # Return a single point with today's date
        today = datetime.date.today()

        points = [DataPoint(date=today, value=value)]

        # Apply date filters (though typically won't filter anything)
        if start and points[0].date < start:
            points = []
        if end and points and points[0].date > end:
            points = []

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "subreddit": subreddit,
                "display_name": data.get("display_name_prefixed", f"r/{subreddit}"),
                "title": data.get("title", ""),
                "metric": metric,
                "metric_label": metric_label,
                "description": data.get("public_description", "")[:200],
                "created_utc": data.get("created_utc"),
                "note": "Reddit API provides current snapshot only",
            },
        )
