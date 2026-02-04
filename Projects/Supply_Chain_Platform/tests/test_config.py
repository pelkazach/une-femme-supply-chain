"""Tests for application configuration."""

from src.config import Settings


def test_settings_defaults() -> None:
    """Test that settings have expected default values."""
    settings = Settings()
    assert settings.api_port == 8000
    assert settings.debug is False
    assert "postgresql" in settings.database_url
