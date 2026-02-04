"""Tests for QuickBooks Online API client."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from intuitlib.exceptions import AuthClientError
from quickbooks.exceptions import QuickbooksException

from src.services.quickbooks import (
    QuickBooksAPIError,
    QuickBooksAuthError,
    QuickBooksClient,
    QuickBooksRateLimitError,
    SyncResult,
    TokenData,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_token_file(tmp_path: Path) -> Path:
    """Create a temporary token file path."""
    return tmp_path / "quickbooks_token.json"


@pytest.fixture
def valid_token_data() -> TokenData:
    """Create valid token data."""
    now = datetime.now(UTC)
    return TokenData(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        realm_id="1234567890",
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=100),
    )


@pytest.fixture
def valid_token_file(tmp_path: Path, valid_token_data: TokenData) -> Path:
    """Create a temporary token file with valid token."""
    token_file = tmp_path / "quickbooks_token.json"
    token_file.write_text(json.dumps(valid_token_data.to_dict()))
    return token_file


@pytest.fixture
def expired_access_token_data() -> TokenData:
    """Create token data with expired access token but valid refresh token."""
    now = datetime.now(UTC)
    return TokenData(
        access_token="expired_access_token",
        refresh_token="valid_refresh_token",
        realm_id="1234567890",
        access_token_expires_at=now - timedelta(hours=1),  # Expired
        refresh_token_expires_at=now + timedelta(days=50),  # Still valid
    )


@pytest.fixture
def expired_refresh_token_data() -> TokenData:
    """Create token data with expired refresh token."""
    now = datetime.now(UTC)
    return TokenData(
        access_token="expired_access_token",
        refresh_token="expired_refresh_token",
        realm_id="1234567890",
        access_token_expires_at=now - timedelta(hours=1),
        refresh_token_expires_at=now - timedelta(days=1),  # Expired
    )


@pytest.fixture
def client(temp_token_file: Path) -> QuickBooksClient:
    """Create a QuickBooks client for testing."""
    return QuickBooksClient(
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8000/callback",
        environment="sandbox",
        token_file=temp_token_file,
    )


# ============================================================================
# TokenData Tests
# ============================================================================


class TestTokenData:
    """Tests for TokenData dataclass."""

    def test_to_dict(self, valid_token_data: TokenData) -> None:
        """Test converting token data to dictionary."""
        data = valid_token_data.to_dict()

        assert data["access_token"] == "test_access_token"
        assert data["refresh_token"] == "test_refresh_token"
        assert data["realm_id"] == "1234567890"
        assert "access_token_expires_at" in data
        assert "refresh_token_expires_at" in data
        assert "created_at" in data

    def test_from_dict(self, valid_token_data: TokenData) -> None:
        """Test creating token data from dictionary."""
        data = valid_token_data.to_dict()
        restored = TokenData.from_dict(data)

        assert restored.access_token == valid_token_data.access_token
        assert restored.refresh_token == valid_token_data.refresh_token
        assert restored.realm_id == valid_token_data.realm_id

    def test_access_token_expired_false(self, valid_token_data: TokenData) -> None:
        """Test access_token_expired returns False for valid token."""
        assert valid_token_data.access_token_expired is False

    def test_access_token_expired_true(
        self, expired_access_token_data: TokenData
    ) -> None:
        """Test access_token_expired returns True for expired token."""
        assert expired_access_token_data.access_token_expired is True

    def test_access_token_expired_with_buffer(self) -> None:
        """Test access_token_expired considers 60s buffer."""
        now = datetime.now(UTC)
        token = TokenData(
            access_token="test",
            refresh_token="test",
            realm_id="123",
            access_token_expires_at=now + timedelta(seconds=30),  # Within buffer
            refresh_token_expires_at=now + timedelta(days=100),
        )
        assert token.access_token_expired is True

    def test_refresh_token_expired_false(self, valid_token_data: TokenData) -> None:
        """Test refresh_token_expired returns False for valid token."""
        assert valid_token_data.refresh_token_expired is False

    def test_refresh_token_expired_true(
        self, expired_refresh_token_data: TokenData
    ) -> None:
        """Test refresh_token_expired returns True for expired token."""
        assert expired_refresh_token_data.refresh_token_expired is True


# ============================================================================
# SyncResult Tests
# ============================================================================


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_default_values(self) -> None:
        """Test SyncResult has correct default values."""
        result = SyncResult()
        assert result.success == 0
        assert result.failed == 0
        assert result.errors == []

    def test_with_values(self) -> None:
        """Test SyncResult with custom values."""
        errors = [{"sku": "TEST", "error": "Not found"}]
        result = SyncResult(success=5, failed=1, errors=errors)
        assert result.success == 5
        assert result.failed == 1
        assert len(result.errors) == 1


# ============================================================================
# Client Initialization Tests
# ============================================================================


class TestQuickBooksClientInit:
    """Tests for QuickBooksClient initialization."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default settings."""
        with patch("src.services.quickbooks.settings") as mock_settings:
            mock_settings.quickbooks_client_id = "default_id"
            mock_settings.quickbooks_client_secret = "default_secret"
            mock_settings.quickbooks_redirect_uri = "http://localhost/callback"
            mock_settings.quickbooks_environment = "sandbox"
            mock_settings.quickbooks_token_file = "token.json"

            client = QuickBooksClient()

            assert client.client_id == "default_id"
            assert client.client_secret == "default_secret"
            assert client.redirect_uri == "http://localhost/callback"
            assert client.environment == "sandbox"

    def test_init_with_custom_values(self, temp_token_file: Path) -> None:
        """Test client initialization with custom values."""
        client = QuickBooksClient(
            client_id="custom_id",
            client_secret="custom_secret",
            redirect_uri="http://custom/callback",
            environment="production",
            token_file=temp_token_file,
        )

        assert client.client_id == "custom_id"
        assert client.client_secret == "custom_secret"
        assert client.redirect_uri == "http://custom/callback"
        assert client.environment == "production"
        assert client.token_file == temp_token_file

    def test_is_authenticated_false_by_default(self, client: QuickBooksClient) -> None:
        """Test that client is not authenticated by default."""
        assert client.is_authenticated is False

    def test_needs_token_refresh_true_by_default(
        self, client: QuickBooksClient
    ) -> None:
        """Test that token refresh is needed when no token exists."""
        assert client.needs_token_refresh is True


# ============================================================================
# Authorization URL Tests
# ============================================================================


class TestGetAuthorizationUrl:
    """Tests for get_authorization_url method."""

    def test_returns_url_and_state(self, client: QuickBooksClient) -> None:
        """Test get_authorization_url returns URL and state."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.get_authorization_url.return_value = (
                "https://appcenter.intuit.com/connect/oauth2?..."
            )
            mock_get_client.return_value = mock_auth_client

            url, state = client.get_authorization_url()

            assert url.startswith("https://appcenter.intuit.com")
            assert len(state) > 0
            mock_auth_client.get_authorization_url.assert_called_once()

    def test_uses_provided_state(self, client: QuickBooksClient) -> None:
        """Test get_authorization_url uses provided state."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.get_authorization_url.return_value = "https://..."
            mock_get_client.return_value = mock_auth_client

            _, state = client.get_authorization_url(state="custom_state")

            assert state == "custom_state"


# ============================================================================
# Token Exchange Tests
# ============================================================================


class TestExchangeCode:
    """Tests for exchange_code method."""

    @pytest.mark.asyncio
    async def test_exchange_code_success(self, client: QuickBooksClient) -> None:
        """Test successful authorization code exchange."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.access_token = "new_access_token"
            mock_auth_client.refresh_token = "new_refresh_token"
            mock_get_client.return_value = mock_auth_client

            token_data = await client.exchange_code("auth_code", "1234567890")

            assert token_data.access_token == "new_access_token"
            assert token_data.refresh_token == "new_refresh_token"
            assert token_data.realm_id == "1234567890"
            assert client.is_authenticated is True

    @pytest.mark.asyncio
    async def test_exchange_code_saves_token(
        self, client: QuickBooksClient, temp_token_file: Path
    ) -> None:
        """Test that exchange_code saves token to file."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.access_token = "new_access_token"
            mock_auth_client.refresh_token = "new_refresh_token"
            mock_get_client.return_value = mock_auth_client

            await client.exchange_code("auth_code", "1234567890")

            assert temp_token_file.exists()
            saved_data = json.loads(temp_token_file.read_text())
            assert saved_data["access_token"] == "new_access_token"

    @pytest.mark.asyncio
    async def test_exchange_code_failure(self, client: QuickBooksClient) -> None:
        """Test exchange_code handles authentication failures."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            # AuthClientError expects a response object with status_code
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid code"
            mock_auth_client.get_bearer_token.side_effect = AuthClientError(mock_response)
            mock_get_client.return_value = mock_auth_client

            with pytest.raises(QuickBooksAuthError, match="Token exchange failed"):
                await client.exchange_code("invalid_code", "1234567890")


# ============================================================================
# Token Refresh Tests
# ============================================================================


class TestRefreshTokens:
    """Tests for refresh_tokens method."""

    @pytest.mark.asyncio
    async def test_refresh_tokens_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test successful token refresh."""
        client._token_data = valid_token_data

        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.access_token = "refreshed_access_token"
            mock_auth_client.refresh_token = "refreshed_refresh_token"
            mock_get_client.return_value = mock_auth_client

            new_token_data = await client.refresh_tokens()

            assert new_token_data.access_token == "refreshed_access_token"

    @pytest.mark.asyncio
    async def test_refresh_tokens_no_token(self, client: QuickBooksClient) -> None:
        """Test refresh_tokens fails when no token exists."""
        with pytest.raises(QuickBooksAuthError, match="No token data to refresh"):
            await client.refresh_tokens()

    @pytest.mark.asyncio
    async def test_refresh_tokens_expired_refresh(
        self, client: QuickBooksClient, expired_refresh_token_data: TokenData
    ) -> None:
        """Test refresh_tokens fails when refresh token is expired."""
        client._token_data = expired_refresh_token_data

        with pytest.raises(QuickBooksAuthError, match="Refresh token has expired"):
            await client.refresh_tokens()

    @pytest.mark.asyncio
    async def test_refresh_tokens_auth_error(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test refresh_tokens handles authentication errors."""
        client._token_data = valid_token_data

        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            # AuthClientError expects a response object with status_code
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Refresh failed"
            mock_auth_client.refresh.side_effect = AuthClientError(mock_response)
            mock_get_client.return_value = mock_auth_client

            with pytest.raises(QuickBooksAuthError, match="Token refresh failed"):
                await client.refresh_tokens()


# ============================================================================
# Load Token Tests
# ============================================================================


class TestLoadToken:
    """Tests for load_token method."""

    def test_load_token_file_not_found(self, client: QuickBooksClient) -> None:
        """Test load_token returns False when file doesn't exist."""
        assert client.load_token() is False

    def test_load_token_invalid_json(
        self, client: QuickBooksClient, temp_token_file: Path
    ) -> None:
        """Test load_token handles invalid JSON."""
        temp_token_file.write_text("not valid json")
        assert client.load_token() is False

    def test_load_token_success(
        self, client: QuickBooksClient, valid_token_file: Path
    ) -> None:
        """Test load_token successfully loads valid token."""
        client.token_file = valid_token_file
        assert client.load_token() is True
        assert client.is_authenticated is True

    def test_load_token_expired_refresh(
        self, client: QuickBooksClient, tmp_path: Path, expired_refresh_token_data: TokenData
    ) -> None:
        """Test load_token returns False for expired refresh token."""
        token_file = tmp_path / "expired_token.json"
        token_file.write_text(json.dumps(expired_refresh_token_data.to_dict()))
        client.token_file = token_file

        assert client.load_token() is False
        assert client.is_authenticated is False


# ============================================================================
# QBClient Property Tests
# ============================================================================


class TestQBClientProperty:
    """Tests for qb_client property."""

    def test_qb_client_not_authenticated(self, client: QuickBooksClient) -> None:
        """Test qb_client raises when not authenticated."""
        with pytest.raises(QuickBooksAuthError, match="Not authenticated"):
            _ = client.qb_client


# ============================================================================
# API Call Tests
# ============================================================================


class TestAPICallWithRetry:
    """Tests for _api_call_with_retry method."""

    @pytest.mark.asyncio
    async def test_successful_call(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test successful API call."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        mock_func = MagicMock(return_value="result")

        result = await client._api_call_with_retry(mock_func)

        assert result == "result"
        mock_func.assert_called_once()

    @pytest.mark.asyncio
    async def test_401_triggers_refresh(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test 401 error triggers token refresh."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        call_count = 0

        def mock_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise QuickbooksException("401 Unauthorized")
            return "success"

        with patch.object(client, "refresh_tokens", new_callable=AsyncMock) as mock_refresh:
            result = await client._api_call_with_retry(mock_func)

            assert result == "success"
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_429_retries_with_backoff(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test 429 error retries with exponential backoff."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        call_count = 0

        def mock_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise QuickbooksException("429 Too Many Requests")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._api_call_with_retry(mock_func, max_retries=3)

            assert result == "success"
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_429_raises_after_max_retries(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test 429 error raises after max retries."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        def mock_func() -> str:
            raise QuickbooksException("429 Too Many Requests")

        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(QuickBooksRateLimitError):
            await client._api_call_with_retry(mock_func, max_retries=2)

    @pytest.mark.asyncio
    async def test_500_retries(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test 5xx error retries."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        call_count = 0

        def mock_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise QuickbooksException("500 Internal Server Error")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await client._api_call_with_retry(mock_func)

            assert result == "success"
            assert call_count == 2


# ============================================================================
# Get Items Tests
# ============================================================================


class TestGetItems:
    """Tests for get_items method."""

    @pytest.mark.asyncio
    async def test_get_items_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test getting items successfully."""
        client._token_data = valid_token_data

        mock_items = [MagicMock(Name="Item1"), MagicMock(Name="Item2")]

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = mock_items

            items = await client.get_items()

            assert len(items) == 2
            mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_items_empty(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test get_items returns empty list when no items."""
        client._token_data = valid_token_data

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = None

            items = await client.get_items()

            assert items == []


# ============================================================================
# Get Item by Name Tests
# ============================================================================


class TestGetItemByName:
    """Tests for get_item_by_name method."""

    @pytest.mark.asyncio
    async def test_get_item_by_name_found(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test getting an item by name."""
        client._token_data = valid_token_data

        mock_item = MagicMock(Name="UFBub250")

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = [mock_item]

            item = await client.get_item_by_name("UFBub250")

            assert item == mock_item

    @pytest.mark.asyncio
    async def test_get_item_by_name_not_found(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test getting an item that doesn't exist."""
        client._token_data = valid_token_data

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = []

            item = await client.get_item_by_name("NonExistent")

            assert item is None


# ============================================================================
# Update Item Quantity Tests
# ============================================================================


class TestUpdateItemQuantity:
    """Tests for update_item_quantity method."""

    @pytest.mark.asyncio
    async def test_update_item_quantity_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test updating item quantity successfully."""
        client._token_data = valid_token_data

        mock_item = MagicMock(Name="UFBub250", QtyOnHand=100)

        with patch.object(client, "get_item_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_item

            with patch.object(
                client, "_api_call_with_retry", new_callable=AsyncMock
            ) as mock_call:
                mock_call.return_value = mock_item

                result = await client.update_item_quantity("UFBub250", 150)

                assert result == mock_item

    @pytest.mark.asyncio
    async def test_update_item_quantity_not_found(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test updating non-existent item raises error."""
        client._token_data = valid_token_data

        with patch.object(client, "get_item_by_name", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(QuickBooksAPIError, match="Item not found"):
                await client.update_item_quantity("NonExistent", 100)


# ============================================================================
# Sync Inventory Tests
# ============================================================================


class TestSyncInventory:
    """Tests for sync_inventory method."""

    @pytest.mark.asyncio
    async def test_sync_inventory_all_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test syncing inventory with all successful updates."""
        client._token_data = valid_token_data

        products = [
            {"sku": "UFBub250", "quantity": 100},
            {"sku": "UFRos250", "quantity": 200},
        ]

        with patch.object(
            client, "update_item_quantity", new_callable=AsyncMock
        ) as mock_update:
            mock_update.return_value = MagicMock()

            result = await client.sync_inventory(products)

            assert result.success == 2
            assert result.failed == 0
            assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_sync_inventory_partial_failure(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test syncing inventory with some failures."""
        client._token_data = valid_token_data

        products = [
            {"sku": "UFBub250", "quantity": 100},
            {"sku": "Invalid", "quantity": 200},
        ]

        async def mock_update(name: str, qty: int) -> MagicMock:
            if name == "Invalid":
                raise QuickBooksAPIError("Item not found")
            return MagicMock()

        with patch.object(
            client, "update_item_quantity", side_effect=mock_update
        ):
            result = await client.sync_inventory(products)

            assert result.success == 1
            assert result.failed == 1
            assert len(result.errors) == 1
            assert result.errors[0]["sku"] == "Invalid"


# ============================================================================
# Get Invoices Tests
# ============================================================================


class TestGetInvoices:
    """Tests for get_invoices method."""

    @pytest.mark.asyncio
    async def test_get_invoices_all(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test getting all invoices."""
        client._token_data = valid_token_data

        mock_invoices = [MagicMock(Id="1"), MagicMock(Id="2")]

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = mock_invoices

            invoices = await client.get_invoices()

            assert len(invoices) == 2

    @pytest.mark.asyncio
    async def test_get_invoices_since_date(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test getting invoices since a specific date."""
        client._token_data = valid_token_data

        since = datetime(2026, 1, 1, tzinfo=UTC)

        with patch.object(
            client, "_api_call_with_retry", new_callable=AsyncMock
        ) as mock_call:
            mock_call.return_value = []

            await client.get_invoices(since=since)

            mock_call.assert_called_once()


# ============================================================================
# Test Connection Tests
# ============================================================================


class TestTestConnection:
    """Tests for test_connection method."""

    @pytest.mark.asyncio
    async def test_connection_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test successful connection test."""
        client._token_data = valid_token_data

        with patch.object(client, "get_items", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = []

            result = await client.test_connection()

            assert result is True

    @pytest.mark.asyncio
    async def test_connection_not_authenticated(
        self, client: QuickBooksClient
    ) -> None:
        """Test connection test fails when not authenticated."""
        with pytest.raises(QuickBooksAuthError, match="Not authenticated"):
            await client.test_connection()

    @pytest.mark.asyncio
    async def test_connection_api_error(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test connection test handles API errors."""
        client._token_data = valid_token_data

        with patch.object(client, "get_items", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = QuickBooksAPIError("Connection failed")

            with pytest.raises(QuickBooksAPIError):
                await client.test_connection()


# ============================================================================
# Revoke Token Tests
# ============================================================================


class TestRevokeToken:
    """Tests for revoke_token method."""

    def test_revoke_no_token(self, client: QuickBooksClient) -> None:
        """Test revoking when no token exists."""
        assert client.revoke_token() is False

    def test_revoke_success(
        self, client: QuickBooksClient, valid_token_data: TokenData, tmp_path: Path
    ) -> None:
        """Test successful token revocation."""
        token_file = tmp_path / "token.json"
        token_file.write_text(json.dumps(valid_token_data.to_dict()))

        client._token_data = valid_token_data
        client.token_file = token_file

        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_get_client.return_value = mock_auth_client

            result = client.revoke_token()

            assert result is True
            assert not token_file.exists()
            assert client._token_data is None

    def test_revoke_failure(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test token revocation failure."""
        client._token_data = valid_token_data

        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            # AuthClientError expects a response object with status_code
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.text = "Revoke failed"
            mock_auth_client.revoke.side_effect = AuthClientError(mock_response)
            mock_get_client.return_value = mock_auth_client

            result = client.revoke_token()

            assert result is False


# ============================================================================
# Get Token Info Tests
# ============================================================================


class TestGetTokenInfo:
    """Tests for get_token_info method."""

    def test_get_token_info_no_token(self, client: QuickBooksClient) -> None:
        """Test get_token_info returns None when no token."""
        assert client.get_token_info() is None

    def test_get_token_info_success(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """Test get_token_info returns correct data."""
        client._token_data = valid_token_data

        info = client.get_token_info()

        assert info is not None
        assert info["realm_id"] == "1234567890"
        assert "access_token_expires_at" in info
        assert "refresh_token_expires_at" in info
        assert info["access_token_expired"] is False
        assert info["refresh_token_expired"] is False


# ============================================================================
# Rate Limiting Tests
# ============================================================================


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_not_exceeded(self, client: QuickBooksClient) -> None:
        """Test rate limiting when under limit."""
        # Just make sure _rate_limit doesn't block when under limit
        await client._rate_limit()
        assert len(client._request_timestamps) == 1

    @pytest.mark.asyncio
    async def test_rate_limit_cleans_old_timestamps(
        self, client: QuickBooksClient
    ) -> None:
        """Test that old timestamps are cleaned up."""
        import time

        # Add old timestamps (>60s ago)
        old_time = time.time() - 65
        client._request_timestamps = [old_time] * 10

        await client._rate_limit()

        # Old timestamps should be removed
        assert len(client._request_timestamps) == 1


# ============================================================================
# Acceptance Criteria Tests
# ============================================================================


class TestAcceptanceCriteria:
    """Tests verifying acceptance criteria from spec."""

    @pytest.mark.asyncio
    async def test_oauth_flow_completes(self, client: QuickBooksClient) -> None:
        """AC: OAuth 2.0 flow completes successfully."""
        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.access_token = "access_token"
            mock_auth_client.refresh_token = "refresh_token"
            mock_auth_client.get_authorization_url.return_value = "https://..."
            mock_get_client.return_value = mock_auth_client

            # Step 1: Get authorization URL
            url, state = client.get_authorization_url()
            assert url.startswith("https://")

            # Step 2: Exchange code for tokens
            token_data = await client.exchange_code("auth_code", "realm_id")
            assert token_data.access_token == "access_token"
            assert token_data.refresh_token == "refresh_token"

    @pytest.mark.asyncio
    async def test_token_refresh_automatic(
        self, client: QuickBooksClient, expired_access_token_data: TokenData
    ) -> None:
        """AC: Token refresh happens automatically before expiry."""
        client._token_data = expired_access_token_data
        client._qb_client = MagicMock()

        with patch.object(client, "_get_auth_client") as mock_get_client:
            mock_auth_client = MagicMock()
            mock_auth_client.access_token = "new_access_token"
            mock_auth_client.refresh_token = "new_refresh_token"
            mock_get_client.return_value = mock_auth_client

            with patch.object(
                client, "_api_call_with_retry", wraps=client._api_call_with_retry
            ):
                # The _ensure_valid_token call should trigger refresh
                await client._ensure_valid_token()

                # Token should be refreshed
                assert client._token_data is not None
                assert client._token_data.access_token == "new_access_token"

    def test_tokens_stored_in_file(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """AC: Access + refresh tokens stored."""
        client._token_data = valid_token_data
        client._save_token()

        assert client.token_file.exists()
        saved_data = json.loads(client.token_file.read_text())
        assert "access_token" in saved_data
        assert "refresh_token" in saved_data

    @pytest.mark.asyncio
    async def test_rate_limit_handled_gracefully(
        self, client: QuickBooksClient, valid_token_data: TokenData
    ) -> None:
        """AC: Rate limiting handled gracefully."""
        client._token_data = valid_token_data
        client._qb_client = MagicMock()

        call_count = 0

        def mock_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise QuickbooksException("429 Too Many Requests")
            return "success"

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await client._api_call_with_retry(mock_func, max_retries=3)

            assert result == "success"
            # Should have backed off twice
            assert mock_sleep.call_count >= 2

    def test_sandbox_environment_supported(self) -> None:
        """AC: Sandbox environment supported for testing."""
        client = QuickBooksClient(
            client_id="test",
            client_secret="test",
            redirect_uri="http://localhost",
            environment="sandbox",
        )
        assert client.environment == "sandbox"

    def test_production_environment_supported(self) -> None:
        """AC: Production environment supported."""
        client = QuickBooksClient(
            client_id="test",
            client_secret="test",
            redirect_uri="http://localhost",
            environment="production",
        )
        assert client.environment == "production"
