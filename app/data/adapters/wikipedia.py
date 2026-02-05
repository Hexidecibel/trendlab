"""Wikipedia page views adapter — article traffic trends."""

import datetime

import httpx

from app.data.base import DataAdapter
from app.logging_config import get_logger
from app.models.schemas import (
    DataPoint,
    FormField,
    FormFieldOption,
    LookupItem,
    TimeSeries,
)

logger = get_logger(__name__)

# Wikimedia REST API base URL
WIKIMEDIA_API = "https://wikimedia.org/api/rest_v1"

# Supported Wikipedia projects
PROJECTS = [
    ("en.wikipedia", "English Wikipedia"),
    ("es.wikipedia", "Spanish Wikipedia"),
    ("de.wikipedia", "German Wikipedia"),
    ("fr.wikipedia", "French Wikipedia"),
    ("ja.wikipedia", "Japanese Wikipedia"),
    ("zh.wikipedia", "Chinese Wikipedia"),
    ("ru.wikipedia", "Russian Wikipedia"),
    ("pt.wikipedia", "Portuguese Wikipedia"),
    ("it.wikipedia", "Italian Wikipedia"),
    ("all-projects", "All Wikimedia Projects"),
]

# Access types
ACCESS_TYPES = [
    ("all-access", "All (Desktop + Mobile)"),
    ("desktop", "Desktop Only"),
    ("mobile-web", "Mobile Web"),
    ("mobile-app", "Mobile App"),
]

# Agent types
AGENT_TYPES = [
    ("all-agents", "All (Users + Bots)"),
    ("user", "Human Users Only"),
    ("spider", "Web Crawlers Only"),
    ("automated", "Automated Traffic"),
]

# Granularity
GRANULARITIES = [
    ("daily", "Daily"),
    ("monthly", "Monthly"),
]


class WikipediaAdapter(DataAdapter):
    name = "wikipedia"
    description = "Wikipedia article page views — traffic trends for any topic"
    aggregation_method = "sum"

    def form_fields(self) -> list[FormField]:
        return [
            FormField(
                name="project",
                label="Wikipedia",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in PROJECTS],
            ),
            FormField(
                name="article",
                label="Article",
                field_type="text",
                placeholder="Python_(programming_language)",
            ),
            FormField(
                name="access",
                label="Access Type",
                field_type="select",
                options=[
                    FormFieldOption(value=v, label=lbl) for v, lbl in ACCESS_TYPES
                ],
            ),
            FormField(
                name="agent",
                label="Agent Type",
                field_type="select",
                options=[FormFieldOption(value=v, label=lbl) for v, lbl in AGENT_TYPES],
            ),
            FormField(
                name="granularity",
                label="Granularity",
                field_type="select",
                options=[
                    FormFieldOption(value=v, label=lbl) for v, lbl in GRANULARITIES
                ],
            ),
        ]

    async def lookup(self, lookup_type: str, **kwargs: str) -> list[LookupItem]:
        """Search Wikipedia for article titles."""
        if lookup_type != "article":
            return []

        # Get search query from kwargs (passed from NL resolution)
        search_term = kwargs.get("search", kwargs.get("article", ""))
        if not search_term:
            return []

        project = kwargs.get("project", "en.wikipedia")
        if project == "all-projects":
            project = "en.wikipedia"

        # Use Wikipedia's search API
        search_url = f"https://{project}.org/w/api.php"
        params = {
            "action": "opensearch",
            "search": search_term,
            "limit": "10",
            "namespace": "0",
            "format": "json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                search_url,
                params=params,
                headers={"User-Agent": "TrendLab/1.0 (trend analysis tool)"},
                timeout=10.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning("Wikipedia search failed: %s", response.status_code)
                return []

        # OpenSearch returns [query, [titles], [descriptions], [urls]]
        data = response.json()
        if len(data) < 2:
            return []

        titles = data[1]
        return [LookupItem(value=self._normalize_title(t), label=t) for t in titles]

    def _normalize_title(self, title: str) -> str:
        """Normalize article title for URL (spaces -> underscores)."""
        return title.replace(" ", "_")

    def _denormalize_title(self, title: str) -> str:
        """Denormalize article title for display."""
        return title.replace("_", " ")

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        """Fetch page view data from Wikimedia REST API.

        Query format: project:article:access:agent:granularity
        Example: en.wikipedia:Python_(programming_language):all-access:user:daily
        """
        parts = query.split(":")
        if len(parts) != 5:
            raise ValueError(
                f"Invalid query format: '{query}'. "
                "Expected 'project:article:access:agent:granularity' "
                "(e.g. 'en.wikipedia:Python_(programming_language):all-access:"
                "user:daily')"
            )

        project, article, access, agent, granularity = parts

        # Validate project
        valid_projects = [p[0] for p in PROJECTS]
        if project not in valid_projects:
            raise ValueError(
                f"Invalid project: '{project}'. Valid: {', '.join(valid_projects)}"
            )

        # Validate access
        valid_access = [a[0] for a in ACCESS_TYPES]
        if access not in valid_access:
            raise ValueError(
                f"Invalid access type: '{access}'. Valid: {', '.join(valid_access)}"
            )

        # Validate agent
        valid_agents = [a[0] for a in AGENT_TYPES]
        if agent not in valid_agents:
            raise ValueError(
                f"Invalid agent type: '{agent}'. Valid: {', '.join(valid_agents)}"
            )

        # Validate granularity
        valid_gran = [g[0] for g in GRANULARITIES]
        if granularity not in valid_gran:
            raise ValueError(
                f"Invalid granularity: '{granularity}'. Valid: {', '.join(valid_gran)}"
            )

        # Default date range: last 365 days for daily, 24 months for monthly
        if not end:
            end = datetime.date.today() - datetime.timedelta(days=1)
        if not start:
            if granularity == "monthly":
                start = end - datetime.timedelta(days=730)  # ~2 years
            else:
                start = end - datetime.timedelta(days=365)

        # Format dates for API (YYYYMMDD or YYYYMM00 for monthly)
        if granularity == "monthly":
            start_str = start.strftime("%Y%m") + "01"
            end_str = end.strftime("%Y%m") + "01"
        else:
            start_str = start.strftime("%Y%m%d")
            end_str = end.strftime("%Y%m%d")

        # Build API URL
        url = (
            f"{WIKIMEDIA_API}/metrics/pageviews/per-article/"
            f"{project}/{access}/{agent}/{article}/{granularity}/"
            f"{start_str}/{end_str}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": "TrendLab/1.0"},
                timeout=30.0,
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                if response.status_code == 404:
                    raise ValueError(
                        f"Article '{self._denormalize_title(article)}' not found "
                        f"on {project}"
                    ) from None
                raise

        data = response.json()
        items = data.get("items", [])

        points = []
        for item in items:
            # Parse timestamp (YYYYMMDDHH format)
            ts = item["timestamp"]
            year = int(ts[:4])
            month = int(ts[4:6])
            day = int(ts[6:8])
            dt = datetime.date(year, month, day)
            views = item["views"]
            points.append(DataPoint(date=dt, value=float(views)))

        # Apply date filters
        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        points.sort(key=lambda p: p.date)

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={
                "project": project,
                "article": self._denormalize_title(article),
                "access": access,
                "agent": agent,
                "granularity": granularity,
            },
        )
