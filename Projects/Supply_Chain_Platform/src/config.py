"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://localhost:5432/une_femme"

    # WineDirect API
    winedirect_client_id: str = ""
    winedirect_client_secret: str = ""
    winedirect_base_url: str = "https://api.winedirect.com"

    # Azure Document Intelligence
    azure_doc_intelligence_endpoint: str = ""
    azure_doc_intelligence_key: str = ""

    # Redis (for Celery)
    redis_url: str = "redis://localhost:6379/0"

    # Slack
    slack_webhook_url: str = ""

    # Gmail API OAuth
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"
    gmail_scopes: list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    # Ollama (local LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mixtral"
    ollama_timeout: int = 60  # seconds

    # Application
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
