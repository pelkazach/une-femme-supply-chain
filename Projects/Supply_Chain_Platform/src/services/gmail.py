"""Gmail API client for email monitoring and classification.

This module implements OAuth 2.0 authentication with the Gmail API
for reading emails and attachments.
"""

import base64
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

from src.config import settings

logger = logging.getLogger(__name__)


class GmailAuthError(Exception):
    """Raised when Gmail authentication fails."""


class GmailAPIError(Exception):
    """Raised when a Gmail API call fails."""


@dataclass
class EmailAttachment:
    """Represents an email attachment."""

    filename: str
    mime_type: str
    size: int
    attachment_id: str
    data: bytes | None = None


@dataclass
class EmailMessage:
    """Represents a Gmail message with parsed fields."""

    message_id: str
    thread_id: str
    subject: str
    sender: str
    to: str
    date: datetime
    snippet: str
    body_preview: str
    labels: list[str]
    attachments: list[EmailAttachment]
    raw_headers: dict[str, str]


class GmailClient:
    """Client for Gmail API with OAuth 2.0 authentication.

    Supports both interactive OAuth flow (for initial setup) and
    token refresh for automated background processing.

    Usage:
        # Interactive setup (first time)
        client = GmailClient()
        client.authenticate()

        # Subsequent use with existing token
        client = GmailClient()
        if client.load_token():
            messages = client.list_messages()
    """

    # Gmail API scopes
    DEFAULT_SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.labels",
    ]

    def __init__(
        self,
        credentials_file: str | Path | None = None,
        token_file: str | Path | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize the Gmail client.

        Args:
            credentials_file: Path to OAuth client credentials JSON file.
                Defaults to settings.gmail_credentials_file.
            token_file: Path to store/load OAuth tokens.
                Defaults to settings.gmail_token_file.
            scopes: Gmail API scopes to request.
                Defaults to settings.gmail_scopes or DEFAULT_SCOPES.
        """
        self.credentials_file = Path(credentials_file or settings.gmail_credentials_file)
        self.token_file = Path(token_file or settings.gmail_token_file)
        self.scopes = scopes or settings.gmail_scopes or self.DEFAULT_SCOPES
        self._credentials: Credentials | None = None
        self._service: Resource | None = None

    @property
    def is_authenticated(self) -> bool:
        """Check if the client has valid credentials."""
        return self._credentials is not None and self._credentials.valid

    def load_token(self) -> bool:
        """Load OAuth token from file if it exists.

        Attempts to refresh expired tokens automatically.

        Returns:
            True if a valid token was loaded, False otherwise.
        """
        if not self.token_file.exists():
            logger.info("Token file not found: %s", self.token_file)
            return False

        try:
            self._credentials = Credentials.from_authorized_user_file(
                str(self.token_file), self.scopes
            )
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("Failed to parse token file: %s", e)
            return False

        # Check if token needs refresh
        if self._credentials.expired and self._credentials.refresh_token:
            try:
                self._credentials.refresh(Request())
                self._save_token()
                logger.info("Refreshed expired OAuth token")
            except RefreshError as e:
                logger.error("Failed to refresh token: %s", e)
                self._credentials = None
                return False

        if self._credentials and self._credentials.valid:
            self._build_service()
            return True

        return False

    def authenticate(self, open_browser: bool = True) -> bool:
        """Run the OAuth 2.0 authentication flow.

        This is an interactive process that requires user consent.
        Use load_token() for automated/headless scenarios.

        Args:
            open_browser: Whether to automatically open the browser
                for user authorization. If False, prints the URL.

        Returns:
            True if authentication succeeded, False otherwise.

        Raises:
            GmailAuthError: If credentials file is missing or invalid.
        """
        if not self.credentials_file.exists():
            raise GmailAuthError(
                f"OAuth credentials file not found: {self.credentials_file}. "
                "Download from Google Cloud Console."
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_file), self.scopes
            )

            if open_browser:
                self._credentials = flow.run_local_server(port=0)
            else:
                # Headless mode - print URL for manual authorization
                auth_url, _ = flow.authorization_url(prompt="consent")
                logger.info("Please visit this URL to authorize: %s", auth_url)
                code = input("Enter the authorization code: ")
                flow.fetch_token(code=code)
                self._credentials = flow.credentials

            self._save_token()
            self._build_service()
            logger.info("Gmail OAuth authentication successful")
            return True

        except Exception as e:
            logger.error("OAuth flow failed: %s", e)
            raise GmailAuthError(f"Authentication failed: {e}") from e

    def _save_token(self) -> None:
        """Save the current credentials to the token file."""
        if self._credentials:
            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            self.token_file.write_text(self._credentials.to_json())
            logger.debug("Saved OAuth token to %s", self.token_file)

    def _build_service(self) -> None:
        """Build the Gmail API service client."""
        if self._credentials:
            self._service = build("gmail", "v1", credentials=self._credentials)

    @property
    def service(self) -> Resource:
        """Get the Gmail API service, raising if not authenticated."""
        if self._service is None:
            raise GmailAuthError(
                "Not authenticated. Call authenticate() or load_token() first."
            )
        return self._service

    def list_messages(
        self,
        query: str = "",
        max_results: int = 100,
        label_ids: list[str] | None = None,
        include_spam_trash: bool = False,
    ) -> list[dict[str, Any]]:
        """List messages matching a query.

        Args:
            query: Gmail search query (e.g., "is:unread", "from:example@gmail.com").
            max_results: Maximum number of messages to return.
            label_ids: Filter by label IDs (e.g., ["INBOX", "UNREAD"]).
            include_spam_trash: Include messages from spam and trash.

        Returns:
            List of message metadata (id, threadId).

        Raises:
            GmailAPIError: If the API call fails.
        """
        try:
            results: list[dict[str, Any]] = []
            page_token: str | None = None

            while len(results) < max_results:
                request_params: dict[str, Any] = {
                    "userId": "me",
                    "maxResults": min(max_results - len(results), 100),
                    "includeSpamTrash": include_spam_trash,
                }

                if query:
                    request_params["q"] = query
                if label_ids:
                    request_params["labelIds"] = label_ids
                if page_token:
                    request_params["pageToken"] = page_token

                response = self.service.users().messages().list(**request_params).execute()

                messages = response.get("messages", [])
                results.extend(messages)

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            return results

        except HttpError as e:
            logger.error("Failed to list messages: %s", e)
            raise GmailAPIError(f"Failed to list messages: {e}") from e

    def get_message(
        self,
        message_id: str,
        format_type: str = "full",
    ) -> EmailMessage:
        """Get a single message by ID.

        Args:
            message_id: The message ID to retrieve.
            format_type: Message format - "full", "metadata", "minimal", or "raw".

        Returns:
            Parsed EmailMessage object.

        Raises:
            GmailAPIError: If the API call fails.
        """
        try:
            response = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format=format_type)
                .execute()
            )

            return self._parse_message(response)

        except HttpError as e:
            logger.error("Failed to get message %s: %s", message_id, e)
            raise GmailAPIError(f"Failed to get message: {e}") from e

    def _parse_message(self, raw_message: dict[str, Any]) -> EmailMessage:
        """Parse a raw Gmail API message into an EmailMessage."""
        headers = {}
        payload = raw_message.get("payload", {})

        for header in payload.get("headers", []):
            name = header.get("name", "").lower()
            value = header.get("value", "")
            headers[name] = value

        # Parse date
        date_str = headers.get("date", "")
        try:
            # Gmail uses RFC 2822 format
            from email.utils import parsedate_to_datetime

            message_date = parsedate_to_datetime(date_str)
        except (ValueError, TypeError):
            message_date = datetime.now(UTC)

        # Extract body preview
        body_preview = raw_message.get("snippet", "")

        # Parse attachments
        attachments = self._extract_attachments(payload)

        return EmailMessage(
            message_id=raw_message["id"],
            thread_id=raw_message.get("threadId", ""),
            subject=headers.get("subject", "(No Subject)"),
            sender=headers.get("from", ""),
            to=headers.get("to", ""),
            date=message_date,
            snippet=raw_message.get("snippet", ""),
            body_preview=body_preview,
            labels=raw_message.get("labelIds", []),
            attachments=attachments,
            raw_headers=headers,
        )

    def _extract_attachments(self, payload: dict[str, Any]) -> list[EmailAttachment]:
        """Extract attachment metadata from message payload."""
        attachments: list[EmailAttachment] = []

        # Check for attachments in main payload body
        body = payload.get("body", {})
        if body.get("attachmentId"):
            filename = payload.get("filename", "")
            if filename:
                attachments.append(
                    EmailAttachment(
                        filename=filename,
                        mime_type=payload.get("mimeType", "application/octet-stream"),
                        size=body.get("size", 0),
                        attachment_id=body["attachmentId"],
                    )
                )

        # Check for attachments in parts (multipart messages)
        for part in payload.get("parts", []):
            # Recurse into each part - this handles both direct attachments
            # and nested multipart structures
            attachments.extend(self._extract_attachments(part))

        return attachments

    def get_attachment(
        self,
        message_id: str,
        attachment_id: str,
    ) -> bytes:
        """Download an attachment by ID.

        Args:
            message_id: The parent message ID.
            attachment_id: The attachment ID.

        Returns:
            The attachment data as bytes.

        Raises:
            GmailAPIError: If the API call fails.
        """
        try:
            response = (
                self.service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            data = response.get("data", "")
            # Gmail uses URL-safe base64 encoding
            return base64.urlsafe_b64decode(data)

        except HttpError as e:
            logger.error(
                "Failed to get attachment %s from message %s: %s",
                attachment_id,
                message_id,
                e,
            )
            raise GmailAPIError(f"Failed to get attachment: {e}") from e

    def get_labels(self) -> list[dict[str, Any]]:
        """Get all labels for the authenticated user.

        Returns:
            List of label objects.

        Raises:
            GmailAPIError: If the API call fails.
        """
        try:
            response = self.service.users().labels().list(userId="me").execute()
            labels: list[dict[str, Any]] = response.get("labels", [])
            return labels
        except HttpError as e:
            logger.error("Failed to list labels: %s", e)
            raise GmailAPIError(f"Failed to list labels: {e}") from e

    def get_profile(self) -> dict[str, Any]:
        """Get the authenticated user's Gmail profile.

        Returns:
            Profile dictionary with emailAddress, messagesTotal, etc.

        Raises:
            GmailAPIError: If the API call fails.
        """
        try:
            profile: dict[str, Any] = (
                self.service.users().getProfile(userId="me").execute()
            )
            return profile
        except HttpError as e:
            logger.error("Failed to get profile: %s", e)
            raise GmailAPIError(f"Failed to get profile: {e}") from e

    def revoke_token(self) -> bool:
        """Revoke the current OAuth token.

        Returns:
            True if revocation succeeded, False otherwise.
        """
        if not self._credentials or not self._credentials.token:
            logger.warning("No token to revoke")
            return False

        try:
            import requests

            requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": self._credentials.token},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            # Delete token file
            if self.token_file.exists():
                self.token_file.unlink()

            self._credentials = None
            self._service = None
            logger.info("OAuth token revoked successfully")
            return True

        except Exception as e:
            logger.error("Failed to revoke token: %s", e)
            return False
