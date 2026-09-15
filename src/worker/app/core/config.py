from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    mapeo_api_url: str = "http://mapeo-api:8000"
    mapeo_api_token: str = ""
    poll_interval_sec: int = 15
    reconciliation_interval_sec: int = 86400
    mock_services: bool = False
    max_concurrency: int = 2
    github_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

