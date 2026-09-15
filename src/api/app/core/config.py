from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    environment: str = "dev"
    frontend_url: str = "http://localhost:3000"
    moodle_auth_url: str = "http://localhost:8000/login/token.php"
    moodle_host_header: str = "localhost:8000"
    mapeo_api_url: str = "http://localhost:8001"
    mapeo_api_token: str = "default_token"
    jwt_secret_key: str = "default_token"
    jwt_algorithm: str = "HS256"
    github_token_agent: str = ""
    github_token: str = ""
    enable_evaluation_agent: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

