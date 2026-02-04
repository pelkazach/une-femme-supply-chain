"""WineDirect API client for inventory and depletion data."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class WineDirectAuthError(Exception):
    """Raised when WineDirect authentication fails."""


class WineDirectAPIError(Exception):
    """Raised when a WineDirect API call fails."""


class WineDirectClient:
    """Async client for WineDirect ANWD REST API.

    Implements Bearer Token authentication with automatic token refresh.
    All API calls use HTTPS as required after Feb 16, 2026.
    """

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize the WineDirect client.

        Args:
            client_id: WineDirect API client ID. Defaults to settings.
            client_secret: WineDirect API client secret. Defaults to settings.
            base_url: API base URL. Defaults to settings.
        """
        self.client_id = client_id or settings.winedirect_client_id
        self.client_secret = client_secret or settings.winedirect_client_secret
        self.base_url = (base_url or settings.winedirect_base_url).rstrip("/")
        self._token: str | None = None
        self._token_expires: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WineDirectClient":
        """Enter async context manager."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit async context manager."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Get the HTTP client, raising if not in context manager."""
        if self._http_client is None:
            raise RuntimeError(
                "WineDirectClient must be used as an async context manager"
            )
        return self._http_client

    def _is_token_valid(self) -> bool:
        """Check if the current token is still valid.

        Returns True if token exists and won't expire in the next 60 seconds.
        """
        if not self._token or not self._token_expires:
            return False
        # Consider token invalid if it expires within 60 seconds
        buffer = timedelta(seconds=60)
        return datetime.now(UTC) < (self._token_expires - buffer)

    async def authenticate(self) -> str:
        """Authenticate with WineDirect and obtain Bearer token.

        Uses the AccessToken endpoint with client credentials grant.

        Returns:
            The Bearer token string.

        Raises:
            WineDirectAuthError: If authentication fails.
        """
        if not self.client_id or not self.client_secret:
            raise WineDirectAuthError(
                "WineDirect client_id and client_secret must be configured"
            )

        url = f"{self.base_url}/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = await self._client.post(url, data=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "WineDirect authentication failed: %s %s",
                e.response.status_code,
                e.response.text,
            )
            raise WineDirectAuthError(
                f"Authentication failed: {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            logger.error("WineDirect authentication request error: %s", e)
            raise WineDirectAuthError(f"Authentication request failed: {e}") from e

        data = response.json()
        self._token = data["access_token"]
        # Calculate expiration time (default to 1 hour if not provided)
        expires_in = data.get("expires_in", 3600)
        self._token_expires = datetime.now(UTC) + timedelta(seconds=expires_in)

        logger.info("WineDirect authentication successful, token expires in %ds", expires_in)
        return self._token

    async def _ensure_authenticated(self) -> str:
        """Ensure we have a valid token, refreshing if needed.

        Returns:
            A valid Bearer token.
        """
        if not self._is_token_valid():
            await self.authenticate()
        return self._token  # type: ignore[return-value]

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        retry_on_401: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated API request.

        Automatically handles token refresh on 401 responses.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (without base URL)
            params: Optional query parameters
            json_data: Optional JSON body
            retry_on_401: Whether to retry with fresh token on 401

        Returns:
            Parsed JSON response.

        Raises:
            WineDirectAPIError: If the API call fails.
        """
        token = await self._ensure_authenticated()
        url = f"{self.base_url}{endpoint}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            response = await self._client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
            )

            # Handle 401 by refreshing token and retrying once
            if response.status_code == 401 and retry_on_401:
                logger.warning("Token expired, refreshing and retrying request")
                self._token = None
                self._token_expires = None
                return await self._request(
                    method, endpoint, params, json_data, retry_on_401=False
                )

            response.raise_for_status()
            return response.json()  # type: ignore[no-any-return]

        except httpx.HTTPStatusError as e:
            logger.error(
                "WineDirect API error: %s %s - %s",
                method,
                endpoint,
                e.response.text,
            )
            raise WineDirectAPIError(
                f"API call failed: {e.response.status_code} - {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            logger.error("WineDirect request error: %s %s - %s", method, endpoint, e)
            raise WineDirectAPIError(f"Request failed: {e}") from e

    async def get_sellable_inventory(self) -> list[dict[str, Any]]:
        """Fetch current sellable inventory positions.

        Returns a list of inventory items with SKU, quantity, and pool data.

        Returns:
            List of inventory position dictionaries.
        """
        response = await self._request("GET", "/v1/inventory/sellable")
        # API may return items directly or wrapped in a data key
        if isinstance(response, list):
            return response
        result: list[dict[str, Any]] = response.get("data", response.get("items", []))
        return result

    async def get_inventory_out(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch depletion events (inventory out) since a timestamp.

        Args:
            since: Start datetime for depletion events. Defaults to 24 hours ago.
            until: End datetime for depletion events. Defaults to now.

        Returns:
            List of depletion event dictionaries.
        """
        if since is None:
            since = datetime.now(UTC) - timedelta(hours=24)
        if until is None:
            until = datetime.now(UTC)

        params = {
            "start_date": since.isoformat(),
            "end_date": until.isoformat(),
        }

        response = await self._request("GET", "/v1/inventory-out", params=params)
        if isinstance(response, list):
            return response
        result: list[dict[str, Any]] = response.get("data", response.get("events", []))
        return result

    async def get_velocity_report(self, days: int = 30) -> dict[str, Any]:
        """Get inventory velocity report for specified lookback period.

        Args:
            days: Lookback period in days. Valid values are 30, 60, or 90.

        Returns:
            Dictionary containing velocity metrics by SKU.

        Raises:
            ValueError: If days is not 30, 60, or 90.
        """
        if days not in (30, 60, 90):
            raise ValueError(f"days must be 30, 60, or 90, got {days}")

        params = {"period_days": days}
        response = await self._request("GET", "/v1/reports/velocity", params=params)
        return response

    @property
    def token(self) -> str | None:
        """Get the current access token (for inspection/debugging)."""
        return self._token

    @property
    def token_expires(self) -> datetime | None:
        """Get the token expiration time (for inspection/debugging)."""
        return self._token_expires
