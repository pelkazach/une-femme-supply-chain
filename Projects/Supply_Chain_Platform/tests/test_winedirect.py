"""Tests for WineDirect API client."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.services.winedirect import (
    WineDirectAPIError,
    WineDirectAuthError,
    WineDirectClient,
)


def make_response(status_code: int, json_data: dict | list) -> httpx.Response:
    """Create a properly formed httpx.Response with a request attached."""
    # Create a mock request so raise_for_status() works
    request = httpx.Request("GET", "https://api.winedirect.com/test")
    return httpx.Response(status_code, json=json_data, request=request)


@pytest.fixture
def client() -> WineDirectClient:
    """Create a WineDirect client for testing."""
    return WineDirectClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        base_url="https://api.winedirect.com",
    )


class TestWineDirectClient:
    """Tests for WineDirectClient."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default settings."""
        client = WineDirectClient()
        assert client.base_url == "https://api.winedirect.com"
        assert client._token is None
        assert client._token_expires is None

    def test_init_with_custom_values(self) -> None:
        """Test client initialization with custom values."""
        client = WineDirectClient(
            client_id="custom_id",
            client_secret="custom_secret",
            base_url="https://custom.winedirect.com/",
        )
        assert client.client_id == "custom_id"
        assert client.client_secret == "custom_secret"
        # Base URL should have trailing slash removed
        assert client.base_url == "https://custom.winedirect.com"

    def test_is_token_valid_no_token(self, client: WineDirectClient) -> None:
        """Test token validity when no token exists."""
        assert client._is_token_valid() is False

    def test_is_token_valid_expired(self, client: WineDirectClient) -> None:
        """Test token validity when token is expired."""
        client._token = "test_token"
        client._token_expires = datetime.now(UTC) - timedelta(hours=1)
        assert client._is_token_valid() is False

    def test_is_token_valid_expiring_soon(self, client: WineDirectClient) -> None:
        """Test token validity when token expires within buffer."""
        client._token = "test_token"
        # Token expires in 30 seconds (within 60 second buffer)
        client._token_expires = datetime.now(UTC) + timedelta(seconds=30)
        assert client._is_token_valid() is False

    def test_is_token_valid_good_token(self, client: WineDirectClient) -> None:
        """Test token validity with a good token."""
        client._token = "test_token"
        client._token_expires = datetime.now(UTC) + timedelta(hours=1)
        assert client._is_token_valid() is True

    async def test_context_manager_required(self, client: WineDirectClient) -> None:
        """Test that client must be used as context manager."""
        with pytest.raises(RuntimeError, match="must be used as an async context manager"):
            _ = client._client


class TestAuthentication:
    """Tests for WineDirect authentication."""

    async def test_authenticate_success(self) -> None:
        """Test successful authentication."""
        mock_response = make_response(
            200,
            {"access_token": "test_token_123", "expires_in": 3600},
        )

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
            base_url="https://api.winedirect.com",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                token = await client.authenticate()

                assert token == "test_token_123"
                assert client._token == "test_token_123"
                assert client._token_expires is not None
                mock_post.assert_called_once()

    async def test_authenticate_missing_credentials(self) -> None:
        """Test authentication fails without credentials."""
        client = WineDirectClient(client_id="", client_secret="")

        async with client:
            with pytest.raises(WineDirectAuthError, match="must be configured"):
                await client.authenticate()

    async def test_authenticate_http_error(self) -> None:
        """Test authentication handles HTTP errors."""
        mock_response = make_response(401, {"error": "invalid_client"})

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = mock_response

                with pytest.raises(WineDirectAuthError, match="401"):
                    await client.authenticate()


class TestAPIRequests:
    """Tests for API request methods."""

    async def test_get_sellable_inventory(self) -> None:
        """Test fetching sellable inventory."""
        inventory_data = [
            {"sku": "UFBub250", "quantity": 100, "pool": "warehouse1"},
            {"sku": "UFRos250", "quantity": 50, "pool": "warehouse1"},
        ]
        auth_response = make_response(
            200, {"access_token": "token123", "expires_in": 3600}
        )
        inventory_response = make_response(200, {"data": inventory_data})

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = inventory_response

                    result = await client.get_sellable_inventory()

                    assert result == inventory_data
                    mock_request.assert_called_once()
                    call_args = mock_request.call_args
                    assert call_args[0][0] == "GET"
                    assert "/inventory/sellable" in call_args[0][1]

    async def test_get_sellable_inventory_list_response(self) -> None:
        """Test fetching sellable inventory when API returns list directly."""
        inventory_data = [
            {"sku": "UFBub250", "quantity": 100},
        ]
        auth_response = make_response(
            200, {"access_token": "token123", "expires_in": 3600}
        )
        inventory_response = make_response(200, inventory_data)

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = inventory_response

                    result = await client.get_sellable_inventory()
                    assert result == inventory_data

    async def test_get_inventory_out(self) -> None:
        """Test fetching depletion events."""
        depletion_data = [
            {"sku": "UFBub250", "quantity": -10, "timestamp": "2026-02-03T10:00:00Z"},
        ]
        auth_response = make_response(
            200, {"access_token": "token123", "expires_in": 3600}
        )
        depletion_response = make_response(200, {"events": depletion_data})

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = depletion_response

                    since = datetime(2026, 2, 1, tzinfo=UTC)
                    until = datetime(2026, 2, 3, tzinfo=UTC)
                    result = await client.get_inventory_out(since=since, until=until)

                    assert result == depletion_data
                    call_args = mock_request.call_args
                    assert "start_date" in call_args[1]["params"]
                    assert "end_date" in call_args[1]["params"]

    async def test_get_velocity_report(self) -> None:
        """Test fetching velocity report."""
        velocity_data = {
            "period_days": 30,
            "skus": [
                {"sku": "UFBub250", "units_per_day": 5.2},
                {"sku": "UFRos250", "units_per_day": 3.1},
            ],
        }
        auth_response = make_response(
            200, {"access_token": "token123", "expires_in": 3600}
        )
        velocity_response = make_response(200, velocity_data)

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = velocity_response

                    result = await client.get_velocity_report(days=30)

                    assert result == velocity_data
                    call_args = mock_request.call_args
                    assert call_args[1]["params"]["period_days"] == 30

    async def test_get_velocity_report_invalid_days(self) -> None:
        """Test velocity report rejects invalid day values."""
        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with pytest.raises(ValueError, match="must be 30, 60, or 90"):
                await client.get_velocity_report(days=45)

    async def test_token_refresh_on_401(self) -> None:
        """Test automatic token refresh on 401 response."""
        auth_response = make_response(
            200, {"access_token": "new_token", "expires_in": 3600}
        )
        unauthorized_response = make_response(401, {"error": "unauthorized"})
        success_response = make_response(200, {"data": []})

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            # Set an "expired" token
            client._token = "old_token"
            client._token_expires = datetime.now(UTC) + timedelta(hours=1)

            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    # First call returns 401, second call succeeds
                    mock_request.side_effect = [unauthorized_response, success_response]

                    result = await client.get_sellable_inventory()

                    assert result == []
                    # Should have made 2 requests (first failed, second succeeded)
                    assert mock_request.call_count == 2
                    # Should have refreshed token
                    mock_post.assert_called_once()

    async def test_api_error_propagated(self) -> None:
        """Test that API errors are properly wrapped."""
        auth_response = make_response(
            200, {"access_token": "token123", "expires_in": 3600}
        )
        error_response = make_response(500, {"error": "internal server error"})

        client = WineDirectClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        async with client:
            with patch.object(
                client._http_client, "post", new_callable=AsyncMock
            ) as mock_post:
                mock_post.return_value = auth_response

                with patch.object(
                    client._http_client, "request", new_callable=AsyncMock
                ) as mock_request:
                    mock_request.return_value = error_response

                    with pytest.raises(WineDirectAPIError, match="500"):
                        await client.get_sellable_inventory()


class TestProperties:
    """Tests for client properties."""

    def test_token_property(self) -> None:
        """Test token property returns current token."""
        client = WineDirectClient()
        assert client.token is None

        client._token = "test_token"
        assert client.token == "test_token"

    def test_token_expires_property(self) -> None:
        """Test token_expires property returns expiration time."""
        client = WineDirectClient()
        assert client.token_expires is None

        expires = datetime.now(UTC) + timedelta(hours=1)
        client._token_expires = expires
        assert client.token_expires == expires
