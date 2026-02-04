import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.github_token: str | None = os.environ.get("GITHUB_TOKEN")
        self.football_data_token: str | None = os.environ.get("FOOTBALL_DATA_TOKEN")
        self.anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        self.debug: str = os.environ.get("DEBUG", "true")
        self.host: str = os.environ.get("HOST", "0.0.0.0")
        self.port: int = int(os.environ.get("PORT", "8000"))


settings = Settings()
