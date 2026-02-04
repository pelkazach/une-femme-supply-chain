"""Tests for database configuration."""

from src.database import Base, get_async_database_url


def test_base_metadata_exists() -> None:
    """Test that Base has metadata attribute."""
    assert hasattr(Base, "metadata")
    assert Base.metadata is not None


def test_get_async_database_url_converts_postgresql() -> None:
    """Test that postgresql:// URLs are converted to postgresql+asyncpg://."""
    url = "postgresql://user:pass@localhost:5432/dbname"
    result = get_async_database_url(url)
    assert result == "postgresql+asyncpg://user:pass@localhost:5432/dbname"


def test_get_async_database_url_preserves_asyncpg() -> None:
    """Test that already async URLs are not modified."""
    url = "postgresql+asyncpg://user:pass@localhost:5432/dbname"
    result = get_async_database_url(url)
    assert result == url


def test_get_async_database_url_preserves_other() -> None:
    """Test that non-postgresql URLs are not modified."""
    url = "sqlite:///test.db"
    result = get_async_database_url(url)
    assert result == url
