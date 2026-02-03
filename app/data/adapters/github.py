import datetime
from collections import Counter

import httpx

from app.data.base import DataAdapter
from app.models.schemas import DataPoint, TimeSeries

GITHUB_API_URL = "https://api.github.com/repos/{owner_repo}/stargazers"


class GitHubStarsAdapter(DataAdapter):
    name = "github_stars"
    description = "GitHub repo stargazers over time"

    def __init__(self, token: str) -> None:
        self._token = token

    async def fetch(
        self,
        query: str,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
    ) -> TimeSeries:
        url = GITHUB_API_URL.format(owner_repo=query)
        headers = {
            "Accept": "application/vnd.github.star+json",
            "Authorization": f"Bearer {self._token}",
        }

        all_stargazers: list[str] = []
        page = 1

        async with httpx.AsyncClient() as client:
            while True:
                response = await client.get(
                    url,
                    headers=headers,
                    params={"per_page": 100, "page": page},
                )

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    if response.status_code == 404:
                        raise ValueError(
                            f"Repository '{query}' not found on GitHub"
                        ) from None
                    if response.status_code == 403:
                        raise ValueError(
                            f"GitHub API rate limit exceeded for '{query}'. "
                            "Check your GITHUB_TOKEN."
                        ) from None
                    raise

                data = response.json()
                if not data:
                    break

                for entry in data:
                    all_stargazers.append(entry["starred_at"])

                page += 1

        # Bucket timestamps into daily counts
        daily_counts: Counter[datetime.date] = Counter()
        for ts_str in all_stargazers:
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            daily_counts[dt.date()] += 1

        points = [
            DataPoint(date=d, value=float(c)) for d, c in sorted(daily_counts.items())
        ]

        if start:
            points = [p for p in points if p.date >= start]
        if end:
            points = [p for p in points if p.date <= end]

        return TimeSeries(
            source=self.name,
            query=query,
            points=points,
            metadata={"total_stars": len(all_stargazers)},
        )
