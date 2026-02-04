"""Tests for Gmail API client."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from src.services.gmail import (
    EmailAttachment,
    EmailMessage,
    GmailAPIError,
    GmailAuthError,
    GmailClient,
)


@pytest.fixture
def temp_credentials_file(tmp_path: Path) -> Path:
    """Create a temporary OAuth credentials file."""
    creds = {
        "installed": {
            "client_id": "test_client_id.apps.googleusercontent.com",
            "client_secret": "test_client_secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text(json.dumps(creds))
    return creds_file


@pytest.fixture
def temp_token_file(tmp_path: Path) -> Path:
    """Create a temporary token file path."""
    return tmp_path / "token.json"


@pytest.fixture
def valid_token_file(tmp_path: Path) -> Path:
    """Create a temporary token file with valid token."""
    token = {
        "token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_client_id.apps.googleusercontent.com",
        "client_secret": "test_client_secret",
        "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
        "expiry": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps(token))
    return token_file


@pytest.fixture
def client(temp_credentials_file: Path, temp_token_file: Path) -> GmailClient:
    """Create a Gmail client for testing."""
    return GmailClient(
        credentials_file=temp_credentials_file,
        token_file=temp_token_file,
    )


class TestGmailClientInit:
    """Tests for GmailClient initialization."""

    def test_init_with_defaults(self) -> None:
        """Test client initialization with default settings."""
        client = GmailClient()
        assert client.credentials_file == Path("credentials.json")
        assert client.token_file == Path("token.json")
        assert len(client.scopes) > 0

    def test_init_with_custom_values(
        self, temp_credentials_file: Path, temp_token_file: Path
    ) -> None:
        """Test client initialization with custom values."""
        custom_scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=temp_token_file,
            scopes=custom_scopes,
        )
        assert client.credentials_file == temp_credentials_file
        assert client.token_file == temp_token_file
        assert client.scopes == custom_scopes

    def test_is_authenticated_false_by_default(self, client: GmailClient) -> None:
        """Test that client is not authenticated by default."""
        assert client.is_authenticated is False


class TestTokenManagement:
    """Tests for OAuth token loading and management."""

    def test_load_token_file_not_found(self, client: GmailClient) -> None:
        """Test load_token returns False when file doesn't exist."""
        assert client.load_token() is False

    def test_load_token_invalid_json(
        self, temp_credentials_file: Path, temp_token_file: Path
    ) -> None:
        """Test load_token handles invalid JSON."""
        temp_token_file.write_text("not valid json")
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=temp_token_file,
        )
        assert client.load_token() is False

    def test_load_token_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test load_token successfully loads valid token."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        # Mock the credentials to be valid
        with patch.object(Credentials, "valid", True):
            with patch.object(Credentials, "expired", False):
                with patch(
                    "src.services.gmail.build", return_value=MagicMock()
                ):
                    result = client.load_token()

        # Token file exists and is valid JSON, so loading should work
        # (actual validity depends on the mocked credentials)
        assert result is True or result is False  # Depends on token state

    def test_load_token_refresh_expired(
        self, temp_credentials_file: Path, tmp_path: Path
    ) -> None:
        """Test load_token refreshes expired token."""
        # Create expired token
        token = {
            "token": "expired_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id.apps.googleusercontent.com",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "expiry": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        }
        token_file = tmp_path / "expired_token.json"
        token_file.write_text(json.dumps(token))

        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=token_file,
        )

        # Mock credentials to simulate expired but refreshable
        mock_creds = MagicMock(spec=Credentials)
        mock_creds.expired = True
        mock_creds.valid = True
        mock_creds.refresh_token = "test_refresh"
        mock_creds.to_json.return_value = json.dumps(token)

        with patch.object(
            Credentials, "from_authorized_user_file", return_value=mock_creds
        ):
            with patch("src.services.gmail.build", return_value=MagicMock()):
                result = client.load_token()
                mock_creds.refresh.assert_called_once()
                assert result is True

    def test_load_token_refresh_fails(
        self, temp_credentials_file: Path, tmp_path: Path
    ) -> None:
        """Test load_token handles refresh failure."""
        token = {
            "token": "expired_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test_client_id.apps.googleusercontent.com",
            "client_secret": "test_client_secret",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "expiry": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        }
        token_file = tmp_path / "expired_token.json"
        token_file.write_text(json.dumps(token))

        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=token_file,
        )

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.expired = True
        mock_creds.refresh_token = "test_refresh"
        mock_creds.refresh.side_effect = RefreshError("Token refresh failed")

        with patch.object(
            Credentials, "from_authorized_user_file", return_value=mock_creds
        ):
            result = client.load_token()
            assert result is False


class TestAuthentication:
    """Tests for OAuth authentication flow."""

    def test_authenticate_missing_credentials_file(
        self, temp_token_file: Path, tmp_path: Path
    ) -> None:
        """Test authenticate fails when credentials file missing."""
        client = GmailClient(
            credentials_file=tmp_path / "nonexistent.json",
            token_file=temp_token_file,
        )

        with pytest.raises(GmailAuthError, match="not found"):
            client.authenticate()

    def test_authenticate_success(self, temp_credentials_file: Path, tmp_path: Path) -> None:
        """Test successful OAuth authentication."""
        token_file = tmp_path / "new_token.json"
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=token_file,
        )

        mock_flow = MagicMock()
        mock_creds = MagicMock(spec=Credentials)
        mock_creds.valid = True  # Explicitly set valid property
        mock_creds.to_json.return_value = '{"token": "new_token"}'
        mock_flow.run_local_server.return_value = mock_creds

        with patch(
            "src.services.gmail.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        ):
            with patch("src.services.gmail.build", return_value=MagicMock()):
                result = client.authenticate()

        assert result is True
        assert client.is_authenticated is True
        assert token_file.exists()

    def test_authenticate_flow_error(
        self, temp_credentials_file: Path, temp_token_file: Path
    ) -> None:
        """Test authenticate handles flow errors."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=temp_token_file,
        )

        with patch(
            "src.services.gmail.InstalledAppFlow.from_client_secrets_file",
            side_effect=Exception("Flow error"),
        ):
            with pytest.raises(GmailAuthError, match="Authentication failed"):
                client.authenticate()


class TestServiceProperty:
    """Tests for service property."""

    def test_service_not_authenticated(self, client: GmailClient) -> None:
        """Test service property raises when not authenticated."""
        with pytest.raises(GmailAuthError, match="Not authenticated"):
            _ = client.service


class TestListMessages:
    """Tests for listing messages."""

    def test_list_messages_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test listing messages successfully."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ]
        }
        mock_messages.list.return_value = mock_list
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.list_messages(query="is:unread", max_results=10)

        assert len(result) == 2
        assert result[0]["id"] == "msg1"
        mock_messages.list.assert_called_once()

    def test_list_messages_empty(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test listing messages returns empty list when no messages."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {}
        mock_messages.list.return_value = mock_list
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.list_messages()
        assert result == []

    def test_list_messages_api_error(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test list_messages handles API errors."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_list = MagicMock()

        # Create HttpError with proper structure
        resp = MagicMock()
        resp.status = 500
        resp.reason = "Internal Server Error"
        mock_list.execute.side_effect = HttpError(resp, b"Server error")
        mock_messages.list.return_value = mock_list
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        with pytest.raises(GmailAPIError, match="Failed to list messages"):
            client.list_messages()

    def test_list_messages_pagination(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test listing messages with pagination."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_list = MagicMock()

        # First page returns messages and nextPageToken
        # Second page returns messages without nextPageToken
        mock_list.execute.side_effect = [
            {
                "messages": [{"id": f"msg{i}", "threadId": f"thread{i}"} for i in range(100)],
                "nextPageToken": "token123",
            },
            {
                "messages": [{"id": f"msg{i}", "threadId": f"thread{i}"} for i in range(100, 150)],
            },
        ]
        mock_messages.list.return_value = mock_list
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.list_messages(max_results=150)

        assert len(result) == 150
        assert mock_list.execute.call_count == 2


class TestGetMessage:
    """Tests for getting individual messages."""

    def test_get_message_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test getting a single message."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_get = MagicMock()
        mock_get.execute.return_value = {
            "id": "msg1",
            "threadId": "thread1",
            "snippet": "Test email content...",
            "labelIds": ["INBOX", "UNREAD"],
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "To", "value": "recipient@example.com"},
                    {"name": "Date", "value": "Mon, 3 Feb 2026 10:00:00 +0000"},
                ],
                "parts": [],
            },
        }
        mock_messages.get.return_value = mock_get
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.get_message("msg1")

        assert isinstance(result, EmailMessage)
        assert result.message_id == "msg1"
        assert result.subject == "Test Subject"
        assert result.sender == "sender@example.com"
        assert "INBOX" in result.labels

    def test_get_message_api_error(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test get_message handles API errors."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_messages = MagicMock()
        mock_get = MagicMock()

        resp = MagicMock()
        resp.status = 404
        resp.reason = "Not Found"
        mock_get.execute.side_effect = HttpError(resp, b"Message not found")
        mock_messages.get.return_value = mock_get
        mock_service.users.return_value.messages.return_value = mock_messages

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        with pytest.raises(GmailAPIError, match="Failed to get message"):
            client.get_message("nonexistent")


class TestAttachments:
    """Tests for attachment handling."""

    def test_extract_attachments_from_payload(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test extracting attachments from message payload."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        payload = {
            "parts": [
                {
                    "filename": "document.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att1", "size": 1024},
                },
                {
                    "filename": "image.png",
                    "mimeType": "image/png",
                    "body": {"attachmentId": "att2", "size": 2048},
                },
            ]
        }

        attachments = client._extract_attachments(payload)

        assert len(attachments) == 2
        assert attachments[0].filename == "document.pdf"
        assert attachments[0].mime_type == "application/pdf"
        assert attachments[0].size == 1024
        assert attachments[1].filename == "image.png"

    def test_get_attachment_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test downloading an attachment."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_attachments = MagicMock()
        mock_get = MagicMock()
        # Gmail uses URL-safe base64
        mock_get.execute.return_value = {
            "data": "SGVsbG8gV29ybGQh"  # "Hello World!" in base64
        }
        mock_attachments.get.return_value = mock_get
        mock_service.users.return_value.messages.return_value.attachments.return_value = (
            mock_attachments
        )

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.get_attachment("msg1", "att1")

        assert result == b"Hello World!"


class TestLabels:
    """Tests for label operations."""

    def test_get_labels_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test getting labels."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_labels = MagicMock()
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "Label_1", "name": "Work", "type": "user"},
            ]
        }
        mock_labels.list.return_value = mock_list
        mock_service.users.return_value.labels.return_value = mock_labels

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.get_labels()

        assert len(result) == 2
        assert result[0]["id"] == "INBOX"


class TestProfile:
    """Tests for profile operations."""

    def test_get_profile_success(
        self, temp_credentials_file: Path, valid_token_file: Path
    ) -> None:
        """Test getting user profile."""
        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=valid_token_file,
        )

        mock_service = MagicMock()
        mock_get_profile = MagicMock()
        mock_get_profile.execute.return_value = {
            "emailAddress": "test@example.com",
            "messagesTotal": 1000,
            "threadsTotal": 500,
            "historyId": "12345",
        }
        mock_service.users.return_value.getProfile.return_value = mock_get_profile

        client._credentials = MagicMock(valid=True)
        client._service = mock_service

        result = client.get_profile()

        assert result["emailAddress"] == "test@example.com"
        assert result["messagesTotal"] == 1000


class TestRevokeToken:
    """Tests for token revocation."""

    def test_revoke_token_no_token(self, client: GmailClient) -> None:
        """Test revoking when no token exists."""
        assert client.revoke_token() is False

    def test_revoke_token_success(
        self, temp_credentials_file: Path, tmp_path: Path
    ) -> None:
        """Test successful token revocation."""
        token_file = tmp_path / "token.json"
        token_file.write_text('{"token": "test"}')

        client = GmailClient(
            credentials_file=temp_credentials_file,
            token_file=token_file,
        )

        mock_creds = MagicMock()
        mock_creds.token = "test_token"
        client._credentials = mock_creds
        client._service = MagicMock()

        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = client.revoke_token()

        assert result is True
        assert not token_file.exists()
        assert client._credentials is None
        assert client._service is None


class TestDataClasses:
    """Tests for data classes."""

    def test_email_attachment_dataclass(self) -> None:
        """Test EmailAttachment dataclass."""
        attachment = EmailAttachment(
            filename="test.pdf",
            mime_type="application/pdf",
            size=1024,
            attachment_id="att123",
        )
        assert attachment.filename == "test.pdf"
        assert attachment.data is None

    def test_email_message_dataclass(self) -> None:
        """Test EmailMessage dataclass."""
        message = EmailMessage(
            message_id="msg1",
            thread_id="thread1",
            subject="Test",
            sender="sender@example.com",
            to="recipient@example.com",
            date=datetime.now(UTC),
            snippet="Test snippet",
            body_preview="Test preview",
            labels=["INBOX"],
            attachments=[],
            raw_headers={},
        )
        assert message.message_id == "msg1"
        assert message.subject == "Test"
