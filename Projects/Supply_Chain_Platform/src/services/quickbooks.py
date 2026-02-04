"""QuickBooks Online API client with OAuth 2.0 authentication.

This module implements OAuth 2.0 authentication with the QuickBooks Online API
for syncing inventory, invoices, and sales data.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from intuitlib.client import AuthClient
from intuitlib.enums import Scopes
from intuitlib.exceptions import AuthClientError
from quickbooks import QuickBooks
from quickbooks.exceptions import QuickbooksException
from quickbooks.objects import Invoice, Item

from src.config import settings

logger = logging.getLogger(__name__)


class QuickBooksAuthError(Exception):
    """Raised when QuickBooks authentication fails."""


class QuickBooksAPIError(Exception):
    """Raised when a QuickBooks API call fails."""


class QuickBooksRateLimitError(QuickBooksAPIError):
    """Raised when QuickBooks rate limit is hit (429)."""


@dataclass
class TokenData:
    """Stored OAuth token data."""

    access_token: str
    refresh_token: str
    realm_id: str
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "realm_id": self.realm_id,
            "access_token_expires_at": self.access_token_expires_at.isoformat(),
            "refresh_token_expires_at": self.refresh_token_expires_at.isoformat(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenData":
        """Create from dictionary."""
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            realm_id=data["realm_id"],
            access_token_expires_at=datetime.fromisoformat(data["access_token_expires_at"]),
            refresh_token_expires_at=datetime.fromisoformat(data["refresh_token_expires_at"]),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now(UTC).isoformat())),
        )

    @property
    def access_token_expired(self) -> bool:
        """Check if access token is expired (with 60s buffer)."""
        return datetime.now(UTC) >= (self.access_token_expires_at - timedelta(seconds=60))

    @property
    def refresh_token_expired(self) -> bool:
        """Check if refresh token is expired (with 5 min buffer)."""
        return datetime.now(UTC) >= (self.refresh_token_expires_at - timedelta(minutes=5))


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: int = 0
    failed: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


class QuickBooksClient:
    """Client for QuickBooks Online API with OAuth 2.0 authentication.

    Supports both interactive OAuth flow (for initial setup) and
    automatic token refresh for automated background processing.

    Usage:
        # Interactive setup (first time)
        client = QuickBooksClient()
        auth_url = client.get_authorization_url()
        # User visits auth_url and authorizes
        await client.exchange_code(auth_code, realm_id)

        # Subsequent use with existing token
        client = QuickBooksClient()
        if client.load_token():
            items = await client.get_items()
    """

    # QuickBooks API scopes
    DEFAULT_SCOPES = [Scopes.ACCOUNTING]

    # Rate limiting: 500 req/min, 10 concurrent connections
    RATE_LIMIT_REQUESTS_PER_MINUTE = 500
    MAX_CONCURRENT_CONNECTIONS = 10

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        environment: str | None = None,
        token_file: str | Path | None = None,
    ) -> None:
        """Initialize the QuickBooks client.

        Args:
            client_id: OAuth client ID. Defaults to settings.quickbooks_client_id.
            client_secret: OAuth client secret. Defaults to settings.quickbooks_client_secret.
            redirect_uri: OAuth redirect URI. Defaults to settings.quickbooks_redirect_uri.
            environment: 'sandbox' or 'production'. Defaults to settings.quickbooks_environment.
            token_file: Path to store/load OAuth tokens. Defaults to settings.quickbooks_token_file.
        """
        self.client_id = client_id or settings.quickbooks_client_id
        self.client_secret = client_secret or settings.quickbooks_client_secret
        self.redirect_uri = redirect_uri or settings.quickbooks_redirect_uri
        self.environment = environment or settings.quickbooks_environment
        self.token_file = Path(token_file or settings.quickbooks_token_file)

        self._token_data: TokenData | None = None
        self._auth_client: AuthClient | None = None
        self._qb_client: QuickBooks | None = None

        # Rate limiting state
        self._request_timestamps: list[float] = []
        self._rate_limit_lock = asyncio.Lock()

    def _get_auth_client(self) -> AuthClient:
        """Get or create the auth client."""
        if self._auth_client is None:
            self._auth_client = AuthClient(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                environment=self.environment,
            )
        return self._auth_client

    @property
    def is_authenticated(self) -> bool:
        """Check if the client has valid credentials."""
        if self._token_data is None:
            return False
        return not self._token_data.refresh_token_expired

    @property
    def needs_token_refresh(self) -> bool:
        """Check if the access token needs refresh."""
        if self._token_data is None:
            return True
        return self._token_data.access_token_expired

    def get_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        """Generate OAuth authorization URL for user consent.

        Args:
            state: Optional state parameter for CSRF protection.

        Returns:
            Tuple of (authorization_url, state).
        """
        auth_client = self._get_auth_client()

        # Generate state if not provided
        if state is None:
            import secrets
            state = secrets.token_urlsafe(32)

        auth_url = auth_client.get_authorization_url(
            scopes=self.DEFAULT_SCOPES,
            state_token=state,
        )

        return auth_url, state

    async def exchange_code(self, auth_code: str, realm_id: str) -> TokenData:
        """Exchange authorization code for tokens.

        Args:
            auth_code: Authorization code from OAuth callback.
            realm_id: QuickBooks company ID from OAuth callback.

        Returns:
            TokenData with access and refresh tokens.

        Raises:
            QuickBooksAuthError: If token exchange fails.
        """
        auth_client = self._get_auth_client()

        try:
            # Run blocking call in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: auth_client.get_bearer_token(auth_code, realm_id=realm_id),
            )

            # Create token data with expiry times
            # Access token expires in 1 hour, refresh token in 100 days
            now = datetime.now(UTC)
            self._token_data = TokenData(
                access_token=auth_client.access_token,
                refresh_token=auth_client.refresh_token,
                realm_id=realm_id,
                access_token_expires_at=now + timedelta(hours=1),
                refresh_token_expires_at=now + timedelta(days=100),
            )

            self._save_token()
            self._build_qb_client()

            logger.info("QuickBooks OAuth token exchange successful")
            return self._token_data

        except AuthClientError as e:
            logger.error("QuickBooks token exchange failed: %s", e)
            raise QuickBooksAuthError(f"Token exchange failed: {e}") from e

    async def refresh_tokens(self) -> TokenData:
        """Refresh access token before expiry.

        Returns:
            Updated TokenData.

        Raises:
            QuickBooksAuthError: If token refresh fails.
        """
        if self._token_data is None:
            raise QuickBooksAuthError("No token data to refresh")

        if self._token_data.refresh_token_expired:
            raise QuickBooksAuthError(
                "Refresh token has expired. Re-authentication required."
            )

        auth_client = self._get_auth_client()
        current_token = self._token_data  # Store for type narrowing

        try:
            # Run blocking call in executor
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: auth_client.refresh(refresh_token=current_token.refresh_token),
            )

            # Update token data
            now = datetime.now(UTC)
            self._token_data = TokenData(
                access_token=auth_client.access_token,
                refresh_token=auth_client.refresh_token or current_token.refresh_token,
                realm_id=current_token.realm_id,
                access_token_expires_at=now + timedelta(hours=1),
                # Refresh token expiry stays the same unless new one issued
                refresh_token_expires_at=current_token.refresh_token_expires_at,
            )

            self._save_token()
            self._build_qb_client()

            logger.info("QuickBooks OAuth token refreshed successfully")
            return self._token_data

        except AuthClientError as e:
            logger.error("QuickBooks token refresh failed: %s", e)
            raise QuickBooksAuthError(f"Token refresh failed: {e}") from e

    def load_token(self) -> bool:
        """Load OAuth token from file if it exists.

        Returns:
            True if a valid token was loaded, False otherwise.
        """
        if not self.token_file.exists():
            logger.info("QuickBooks token file not found: %s", self.token_file)
            return False

        try:
            data = json.loads(self.token_file.read_text())
            self._token_data = TokenData.from_dict(data)

            if self._token_data.refresh_token_expired:
                logger.warning("QuickBooks refresh token has expired")
                self._token_data = None
                return False

            self._build_qb_client()
            logger.info("QuickBooks token loaded from %s", self.token_file)
            return True

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error("Failed to parse QuickBooks token file: %s", e)
            return False

    def _save_token(self) -> None:
        """Save the current token data to file."""
        if self._token_data:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(json.dumps(self._token_data.to_dict(), indent=2))
            logger.debug("Saved QuickBooks token to %s", self.token_file)

    def _build_qb_client(self) -> None:
        """Build the QuickBooks API client."""
        if self._token_data:
            auth_client = self._get_auth_client()
            auth_client.access_token = self._token_data.access_token
            auth_client.refresh_token = self._token_data.refresh_token
            auth_client.realm_id = self._token_data.realm_id

            self._qb_client = QuickBooks(
                auth_client=auth_client,
                refresh_token=self._token_data.refresh_token,
                company_id=self._token_data.realm_id,
            )

    @property
    def qb_client(self) -> QuickBooks:
        """Get the QuickBooks API client, raising if not authenticated."""
        if self._qb_client is None:
            raise QuickBooksAuthError(
                "Not authenticated. Call exchange_code() or load_token() first."
            )
        return self._qb_client

    async def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        if self.needs_token_refresh:
            await self.refresh_tokens()

    async def _rate_limit(self) -> None:
        """Apply rate limiting before making an API call."""
        async with self._rate_limit_lock:
            now = time.time()

            # Remove timestamps older than 1 minute
            self._request_timestamps = [
                ts for ts in self._request_timestamps if now - ts < 60
            ]

            # If at limit, wait until oldest request is >1 min old
            if len(self._request_timestamps) >= self.RATE_LIMIT_REQUESTS_PER_MINUTE:
                oldest = min(self._request_timestamps)
                wait_time = 60 - (now - oldest)
                if wait_time > 0:
                    logger.warning(
                        "QuickBooks rate limit reached, waiting %.2f seconds", wait_time
                    )
                    await asyncio.sleep(wait_time)

            self._request_timestamps.append(time.time())

    async def _api_call_with_retry(
        self,
        func: Any,
        *args: Any,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> Any:
        """Execute an API call with retry logic for rate limits and server errors.

        Args:
            func: The function to call.
            *args: Positional arguments for the function.
            max_retries: Maximum number of retries.
            **kwargs: Keyword arguments for the function.

        Returns:
            The result of the function call.

        Raises:
            QuickBooksAPIError: If the call fails after retries.
        """
        await self._ensure_valid_token()

        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            await self._rate_limit()

            try:
                # Run blocking call in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
                return result

            except QuickbooksException as e:
                last_error = e
                error_str = str(e)

                # Handle 401 - refresh token and retry
                if "401" in error_str:
                    logger.warning("QuickBooks 401 error, refreshing token...")
                    try:
                        await self.refresh_tokens()
                        continue
                    except QuickBooksAuthError:
                        raise QuickBooksAuthError(
                            "Authentication failed. Re-authorization required."
                        ) from e

                # Handle 429 - rate limit
                if "429" in error_str:
                    if attempt < max_retries:
                        wait_time = 2 ** (attempt + 1)  # Exponential backoff
                        logger.warning(
                            "QuickBooks rate limit (429), waiting %d seconds (attempt %d/%d)",
                            wait_time,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    raise QuickBooksRateLimitError(f"Rate limit exceeded: {e}") from e

                # Handle 5xx - server errors
                is_server_error = any(str(code) in error_str for code in range(500, 600))
                if is_server_error and attempt < max_retries:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(
                        "QuickBooks server error, retrying in %d seconds (attempt %d/%d)",
                        wait_time,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Other errors - don't retry
                raise QuickBooksAPIError(f"QuickBooks API error: {e}") from e

        raise QuickBooksAPIError(f"QuickBooks API call failed after {max_retries} retries: {last_error}")

    async def get_items(self, active_only: bool = True) -> list[Item]:
        """Get all inventory items from QuickBooks.

        Args:
            active_only: If True, only return active items.

        Returns:
            List of QuickBooks Item objects.
        """
        def fetch_items() -> list[Item]:
            items: list[Item]
            if active_only:
                items = list(Item.filter(Active=True, qb=self.qb_client))
            else:
                items = list(Item.all(qb=self.qb_client))
            return items

        result = await self._api_call_with_retry(fetch_items)
        return result if result else []

    async def get_item_by_name(self, name: str) -> Item | None:
        """Get a specific item by name.

        Args:
            name: The item name (SKU).

        Returns:
            The Item object or None if not found.
        """
        def fetch_item() -> list[Item]:
            items: list[Item] = list(Item.filter(Name=name, qb=self.qb_client))
            return items

        result = await self._api_call_with_retry(fetch_item)
        return result[0] if result else None

    async def update_item_quantity(self, name: str, quantity: int) -> Item:
        """Update an item's quantity on hand.

        Args:
            name: The item name (SKU).
            quantity: The new quantity.

        Returns:
            The updated Item object.

        Raises:
            QuickBooksAPIError: If the item is not found or update fails.
        """
        item = await self.get_item_by_name(name)
        if item is None:
            raise QuickBooksAPIError(f"Item not found: {name}")

        def update_item() -> Item:
            item.QtyOnHand = quantity
            item.save(qb=self.qb_client)
            return item

        return await self._api_call_with_retry(update_item)

    async def sync_inventory(self, products: list[dict[str, Any]]) -> SyncResult:
        """Sync inventory quantities to QuickBooks.

        Args:
            products: List of dicts with 'sku' and 'quantity' keys.

        Returns:
            SyncResult with success/failure counts and errors.
        """
        result = SyncResult()

        for product in products:
            sku = product.get("sku", "")
            quantity = product.get("quantity", 0)

            try:
                await self.update_item_quantity(sku, quantity)
                result.success += 1
                logger.info("Updated QuickBooks inventory for %s: %d", sku, quantity)

            except QuickBooksAPIError as e:
                result.failed += 1
                result.errors.append({
                    "sku": sku,
                    "error": str(e),
                })
                logger.error("Failed to update inventory for %s: %s", sku, e)

        return result

    async def get_invoices(self, since: datetime | None = None) -> list[Invoice]:
        """Pull invoices from QuickBooks.

        Args:
            since: Only return invoices modified after this time.

        Returns:
            List of QuickBooks Invoice objects.
        """
        def fetch_invoices() -> list[Invoice]:
            invoices: list[Invoice]
            if since:
                # Format for QuickBooks query
                since_str = since.strftime("%Y-%m-%dT%H:%M:%S%z")
                invoices = list(Invoice.filter(
                    MetaData__LastUpdatedTime__gt=since_str,
                    qb=self.qb_client,
                ))
            else:
                invoices = list(Invoice.all(qb=self.qb_client))
            return invoices

        result = await self._api_call_with_retry(fetch_invoices)
        return result if result else []

    async def test_connection(self) -> bool:
        """Test the QuickBooks connection.

        Returns:
            True if connection is successful.

        Raises:
            QuickBooksAuthError: If not authenticated.
            QuickBooksAPIError: If connection fails.
        """
        if not self.is_authenticated:
            raise QuickBooksAuthError("Not authenticated")

        # Try to fetch one item to test connection
        try:
            await self.get_items()
            logger.info("QuickBooks connection test successful")
            return True
        except QuickBooksAPIError as e:
            logger.error("QuickBooks connection test failed: %s", e)
            raise

    def revoke_token(self) -> bool:
        """Revoke the current OAuth token.

        Returns:
            True if revocation succeeded, False otherwise.
        """
        if self._token_data is None:
            logger.warning("No token to revoke")
            return False

        try:
            auth_client = self._get_auth_client()
            auth_client.revoke(token=self._token_data.refresh_token)

            # Delete token file
            if self.token_file.exists():
                self.token_file.unlink()

            self._token_data = None
            self._qb_client = None
            logger.info("QuickBooks OAuth token revoked successfully")
            return True

        except AuthClientError as e:
            logger.error("Failed to revoke QuickBooks token: %s", e)
            return False

    def get_token_info(self) -> dict[str, Any] | None:
        """Get information about the current token.

        Returns:
            Dictionary with token info or None if no token.
        """
        if self._token_data is None:
            return None

        return {
            "realm_id": self._token_data.realm_id,
            "access_token_expires_at": self._token_data.access_token_expires_at.isoformat(),
            "refresh_token_expires_at": self._token_data.refresh_token_expires_at.isoformat(),
            "access_token_expired": self._token_data.access_token_expired,
            "refresh_token_expired": self._token_data.refresh_token_expired,
            "environment": self.environment,
        }
