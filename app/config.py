import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.github_token: str | None = os.environ.get("GITHUB_TOKEN")
        self.football_data_token: str | None = os.environ.get("FOOTBALL_DATA_TOKEN")
        self.anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        self.database_url: str = os.environ.get(
            "DATABASE_URL", "sqlite+aiosqlite:///./trendlab.db"
        )
        self.cache_ttl: dict[str, int] = {
            "crypto": 900,  # 15 minutes
            "pypi": 21600,  # 6 hours
            "asa": 86400,  # 24 hours
            "github_stars": 3600,  # 1 hour
            "football": 86400,  # 24 hours
        }
        self.debug: str = os.environ.get("DEBUG", "true")
        self.host: str = os.environ.get("HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
