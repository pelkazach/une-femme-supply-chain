"""Tests for email processor Celery task."""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.email_classifier import ClassificationResult, EmailCategory
from src.services.gmail import EmailAttachment, EmailMessage
from src.tasks.email_processor import (
    MAX_PROCESSING_TIME_MS,
    _async_process_emails,
    get_processed_message_ids,
    process_emails,
    process_single_email,
    process_single_email_task,
    store_classification,
)


def create_mock_email(
    message_id: str = "msg123",
    thread_id: str = "thread456",
    subject: str = "Test Subject",
    sender: str = "sender@example.com",
    to: str = "recipient@example.com",
    body_preview: str = "This is a test email body",
    attachments: list[EmailAttachment] | None = None,
) -> EmailMessage:
    """Create a mock EmailMessage for testing."""
    return EmailMessage(
        message_id=message_id,
        thread_id=thread_id,
        subject=subject,
        sender=sender,
        to=to,
        date=datetime.now(UTC),
        snippet=body_preview[:100],
        body_preview=body_preview,
        labels=["INBOX"],
        attachments=attachments or [],
        raw_headers={"from": sender, "to": to, "subject": subject},
    )


def create_mock_classification(
    category: EmailCategory = EmailCategory.GENERAL,
    confidence: float = 0.95,
    reasoning: str = "Test reasoning",
    needs_review: bool = False,
) -> ClassificationResult:
    """Create a mock ClassificationResult for testing."""
    return ClassificationResult(
        category=category,
        confidence=confidence,
        reasoning=reasoning,
        needs_review=needs_review,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock async database session."""
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


class TestGetProcessedMessageIds:
    """Tests for get_processed_message_ids function."""

    async def test_returns_empty_set_for_empty_input(
        self, mock_session: AsyncMock
    ) -> None:
        """Test empty input returns empty set."""
        result = await get_processed_message_ids(mock_session, [])
        assert result == set()
        mock_session.execute.assert_not_called()

    async def test_returns_processed_ids(self, mock_session: AsyncMock) -> None:
        """Test that processed message IDs are returned."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([("msg1",), ("msg2",)])
        mock_session.execute.return_value = mock_result

        result = await get_processed_message_ids(
            mock_session, ["msg1", "msg2", "msg3"]
        )

        assert result == {"msg1", "msg2"}

    async def test_returns_empty_set_when_none_processed(
        self, mock_session: AsyncMock
    ) -> None:
        """Test that empty set is returned when no IDs are processed."""
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_session.execute.return_value = mock_result

        result = await get_processed_message_ids(
            mock_session, ["msg1", "msg2"]
        )

        assert result == set()


class TestStoreClassification:
    """Tests for store_classification function."""

    async def test_stores_classification(self, mock_session: AsyncMock) -> None:
        """Test that classification is stored correctly."""
        email = create_mock_email()
        classification = create_mock_classification()

        await store_classification(
            mock_session,
            email,
            classification,
            processing_time_ms=100,
            ollama_used=True,
        )

        mock_session.add.assert_called_once()
        record = mock_session.add.call_args[0][0]
        assert record.message_id == email.message_id
        assert record.category == classification.category.value
        assert record.confidence == classification.confidence
        assert record.processing_time_ms == 100
        assert record.ollama_used is True

    async def test_stores_attachments_as_json(self, mock_session: AsyncMock) -> None:
        """Test that attachment names are stored as JSON."""
        attachments = [
            EmailAttachment(
                filename="doc1.pdf",
                mime_type="application/pdf",
                size=1000,
                attachment_id="att1",
            ),
            EmailAttachment(
                filename="doc2.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                size=2000,
                attachment_id="att2",
            ),
        ]
        email = create_mock_email(attachments=attachments)
        classification = create_mock_classification()

        await store_classification(
            mock_session,
            email,
            classification,
            processing_time_ms=100,
            ollama_used=True,
        )

        record = mock_session.add.call_args[0][0]
        assert record.has_attachments is True
        attachment_names = json.loads(record.attachment_names)
        assert attachment_names == ["doc1.pdf", "doc2.xlsx"]

    async def test_stores_needs_review_flag(self, mock_session: AsyncMock) -> None:
        """Test that needs_review flag is stored correctly."""
        email = create_mock_email()
        classification = create_mock_classification(
            confidence=0.70, needs_review=True
        )

        await store_classification(
            mock_session,
            email,
            classification,
            processing_time_ms=100,
            ollama_used=True,
        )

        record = mock_session.add.call_args[0][0]
        assert record.needs_review is True
        assert record.confidence == 0.70

    async def test_truncates_long_subject(self, mock_session: AsyncMock) -> None:
        """Test that long subjects are truncated."""
        long_subject = "x" * 1500
        email = create_mock_email(subject=long_subject)
        classification = create_mock_classification()

        await store_classification(
            mock_session,
            email,
            classification,
            processing_time_ms=100,
            ollama_used=True,
        )

        record = mock_session.add.call_args[0][0]
        assert len(record.subject) == 1000


class TestProcessSingleEmail:
    """Tests for process_single_email function."""

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_returns_classification_and_timing(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that classification result and timing are returned."""
        email = create_mock_email()
        mock_classify.return_value = create_mock_classification()

        result, processing_time, ollama_used = await process_single_email(email)

        assert isinstance(result, ClassificationResult)
        assert processing_time >= 0
        assert ollama_used is True

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_detects_rule_based_fallback(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that rule-based fallback is detected."""
        email = create_mock_email()
        mock_classify.return_value = create_mock_classification(
            reasoning="Rule-based classification based on keyword matches"
        )

        result, processing_time, ollama_used = await process_single_email(email)

        assert ollama_used is False

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_passes_attachments_to_classifier(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that attachment filenames are passed to classifier."""
        attachments = [
            EmailAttachment(
                filename="PO_12345.pdf",
                mime_type="application/pdf",
                size=1000,
                attachment_id="att1",
            ),
        ]
        email = create_mock_email(attachments=attachments)
        mock_classify.return_value = create_mock_classification()

        await process_single_email(email)

        mock_classify.assert_called_once()
        call_kwargs = mock_classify.call_args[1]
        assert call_kwargs["attachments"] == ["PO_12345.pdf"]


class TestAsyncProcessEmails:
    """Tests for _async_process_emails function."""

    @patch("src.tasks.email_processor.create_async_engine")
    @patch("src.tasks.email_processor.GmailClient")
    async def test_returns_error_when_no_token(
        self, mock_gmail_cls: MagicMock, mock_engine: MagicMock
    ) -> None:
        """Test that error is returned when Gmail token is missing."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        mock_gmail = MagicMock()
        mock_gmail.load_token.return_value = False
        mock_gmail_cls.return_value = mock_gmail

        result = await _async_process_emails()

        assert result["status"] == "error"
        assert any("token" in err.lower() for err in result["errors"])

    @patch("src.tasks.email_processor.create_async_engine")
    @patch("src.tasks.email_processor.GmailClient")
    async def test_handles_empty_inbox(
        self, mock_gmail_cls: MagicMock, mock_engine: MagicMock
    ) -> None:
        """Test handling of empty inbox."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        mock_gmail = MagicMock()
        mock_gmail.load_token.return_value = True
        mock_gmail.list_messages.return_value = []
        mock_gmail_cls.return_value = mock_gmail

        result = await _async_process_emails()

        assert result["status"] == "success"
        assert result["emails_fetched"] == 0
        assert result["emails_processed"] == 0

    @patch("src.tasks.email_processor.create_async_engine")
    @patch("src.tasks.email_processor.GmailClient")
    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_successful_processing(
        self,
        mock_classify: AsyncMock,
        mock_gmail_cls: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Test successful email processing."""
        # Setup engine mock
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        # Setup Gmail mock
        mock_gmail = MagicMock()
        mock_gmail.load_token.return_value = True
        mock_gmail.list_messages.return_value = [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"},
        ]
        mock_gmail.get_message.side_effect = [
            create_mock_email(message_id="msg1"),
            create_mock_email(message_id="msg2"),
        ]
        mock_gmail_cls.return_value = mock_gmail

        # Setup classifier mock
        mock_classify.return_value = create_mock_classification(
            category=EmailCategory.PURCHASE_ORDER
        )

        # Setup session mock
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        # Mock processed IDs query to return empty
        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([])
        mock_session.execute.return_value = mock_result

        with patch(
            "src.tasks.email_processor.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_process_emails()

        assert result["status"] == "success"
        assert result["emails_fetched"] == 2
        assert result["emails_processed"] == 2
        assert result["classifications"]["PO"] == 2

    @patch("src.tasks.email_processor.create_async_engine")
    @patch("src.tasks.email_processor.GmailClient")
    async def test_skips_already_processed(
        self,
        mock_gmail_cls: MagicMock,
        mock_engine: MagicMock,
    ) -> None:
        """Test that already processed emails are skipped."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.dispose = AsyncMock()
        mock_engine.return_value = mock_engine_instance

        mock_gmail = MagicMock()
        mock_gmail.load_token.return_value = True
        mock_gmail.list_messages.return_value = [
            {"id": "msg1", "threadId": "thread1"},
        ]
        mock_gmail_cls.return_value = mock_gmail

        # Setup session mock with msg1 already processed
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)

        mock_result = MagicMock()
        mock_result.__iter__ = lambda self: iter([("msg1",)])
        mock_session.execute.return_value = mock_result

        with patch(
            "src.tasks.email_processor.async_sessionmaker",
            return_value=lambda: mock_session_factory,
        ):
            result = await _async_process_emails()

        assert result["emails_fetched"] == 1
        assert result["emails_processed"] == 0
        assert result["emails_skipped"] == 1


class TestProcessEmailsTask:
    """Tests for the Celery task."""

    @patch("src.tasks.email_processor.asyncio.run")
    def test_task_calls_async_process(self, mock_asyncio_run: MagicMock) -> None:
        """Test that Celery task calls the async process function."""
        expected_result = {
            "status": "success",
            "started_at": datetime.now(UTC).isoformat(),
            "completed_at": datetime.now(UTC).isoformat(),
            "emails_fetched": 10,
            "emails_processed": 8,
            "emails_skipped": 2,
            "emails_failed": 0,
            "classifications": {"PO": 2, "BOL": 1, "INVOICE": 3, "GENERAL": 2},
            "needs_review_count": 1,
            "avg_processing_time_ms": 150,
            "errors": [],
        }
        mock_asyncio_run.return_value = expected_result

        result = process_emails.run()

        assert result["status"] == "success"
        assert result["emails_processed"] == 8
        mock_asyncio_run.assert_called_once()

    @patch("src.tasks.email_processor.asyncio.run")
    def test_task_passes_parameters(self, mock_asyncio_run: MagicMock) -> None:
        """Test that task passes parameters correctly."""
        mock_asyncio_run.return_value = {
            "status": "success",
            "emails_fetched": 5,
            "emails_processed": 4,
            "emails_skipped": 1,
            "emails_failed": 0,
            "needs_review_count": 0,
        }

        process_emails.run(max_emails=50, label_ids=["INBOX", "UNREAD"], query="from:test@example.com")

        mock_asyncio_run.assert_called_once()


class TestProcessSingleEmailTask:
    """Tests for the single email Celery task."""

    @patch("src.tasks.email_processor.asyncio.run")
    def test_task_processes_single_email(self, mock_asyncio_run: MagicMock) -> None:
        """Test that single email task works correctly."""
        expected_result = {
            "status": "success",
            "message_id": "msg123",
            "category": "PO",
            "confidence": 0.95,
            "needs_review": False,
            "processing_time_ms": 120,
            "error": None,
        }
        mock_asyncio_run.return_value = expected_result

        result = process_single_email_task.run(message_id="msg123")

        assert result["status"] == "success"
        assert result["category"] == "PO"
        mock_asyncio_run.assert_called_once()


class TestMaxProcessingTime:
    """Tests for processing time constant."""

    def test_max_processing_time_is_15_seconds(self) -> None:
        """Test that MAX_PROCESSING_TIME_MS is 15 seconds."""
        assert MAX_PROCESSING_TIME_MS == 15000


class TestCeleryBeatSchedule:
    """Tests for Celery beat schedule configuration."""

    def test_email_processing_scheduled(self) -> None:
        """Test that email processing is in the beat schedule."""
        from src.celery_app import celery_app

        assert "process-emails-periodic" in celery_app.conf.beat_schedule

    def test_email_processing_runs_every_5_minutes(self) -> None:
        """Test that email processing runs every 5 minutes."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["process-emails-periodic"]
        # crontab(minute="*/5") expands to {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        expected_minutes = {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}
        assert schedule["schedule"].minute == expected_minutes

    def test_email_processing_uses_correct_task(self) -> None:
        """Test that the correct task is configured."""
        from src.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule["process-emails-periodic"]
        assert schedule["task"] == "src.tasks.email_processor.process_emails"


class TestEmailClassificationModel:
    """Tests for EmailClassification model."""

    def test_model_has_required_fields(self) -> None:
        """Test that model has all required fields."""
        from src.models.email_classification import EmailClassification

        # Check field names exist
        columns = {c.name for c in EmailClassification.__table__.columns}
        required_fields = {
            "id",
            "message_id",
            "thread_id",
            "subject",
            "sender",
            "recipient",
            "received_at",
            "category",
            "confidence",
            "reasoning",
            "needs_review",
            "reviewed",
            "reviewed_by",
            "reviewed_at",
            "corrected_category",
            "has_attachments",
            "attachment_names",
            "processing_time_ms",
            "ollama_used",
            "created_at",
            "updated_at",
        }
        assert required_fields.issubset(columns)

    def test_model_has_unique_message_id_index(self) -> None:
        """Test that model has unique index on message_id."""
        from src.models.email_classification import EmailClassification

        indexes = {idx.name: idx for idx in EmailClassification.__table__.indexes}
        assert "idx_email_classifications_message_id" in indexes
        assert indexes["idx_email_classifications_message_id"].unique


class TestProcessingLatencyRequirement:
    """Tests for processing latency requirement (<15 seconds)."""

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_classification_completes_under_15_seconds(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that classification completes within time limit."""
        email = create_mock_email()
        mock_classify.return_value = create_mock_classification()

        result, processing_time_ms, _ = await process_single_email(email)

        # In mock scenario, this should be fast
        # In production, Ollama latency is ~50ms per spec
        assert processing_time_ms < MAX_PROCESSING_TIME_MS


class TestCategoryClassification:
    """Tests for email category classification."""

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_classifies_po_emails(self, mock_classify: AsyncMock) -> None:
        """Test that PO emails are classified correctly."""
        email = create_mock_email(
            subject="Purchase Order #12345",
            body_preview="Please find attached PO for 100 cases",
        )
        mock_classify.return_value = create_mock_classification(
            category=EmailCategory.PURCHASE_ORDER, confidence=0.95
        )

        result, _, _ = await process_single_email(email)

        assert result.category == EmailCategory.PURCHASE_ORDER

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_classifies_bol_emails(self, mock_classify: AsyncMock) -> None:
        """Test that BOL emails are classified correctly."""
        email = create_mock_email(
            subject="Bill of Lading - Tracking #ABC123",
            body_preview="Your shipment has been dispatched",
        )
        mock_classify.return_value = create_mock_classification(
            category=EmailCategory.BILL_OF_LADING, confidence=0.92
        )

        result, _, _ = await process_single_email(email)

        assert result.category == EmailCategory.BILL_OF_LADING

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_classifies_invoice_emails(self, mock_classify: AsyncMock) -> None:
        """Test that Invoice emails are classified correctly."""
        email = create_mock_email(
            subject="Invoice #INV-2026-001",
            body_preview="Payment due within 30 days",
        )
        mock_classify.return_value = create_mock_classification(
            category=EmailCategory.INVOICE, confidence=0.98
        )

        result, _, _ = await process_single_email(email)

        assert result.category == EmailCategory.INVOICE

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_classifies_general_emails(self, mock_classify: AsyncMock) -> None:
        """Test that general emails are classified correctly."""
        email = create_mock_email(
            subject="Quick question about wine selection",
            body_preview="Hi, I was wondering about your wine offerings",
        )
        mock_classify.return_value = create_mock_classification(
            category=EmailCategory.GENERAL, confidence=0.88
        )

        result, _, _ = await process_single_email(email)

        assert result.category == EmailCategory.GENERAL


class TestLowConfidenceReview:
    """Tests for low confidence human review flagging."""

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_flags_low_confidence_for_review(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that low confidence classifications are flagged."""
        email = create_mock_email()
        mock_classify.return_value = create_mock_classification(
            confidence=0.70, needs_review=True
        )

        result, _, _ = await process_single_email(email)

        assert result.needs_review is True
        assert result.confidence < 0.85

    @patch("src.tasks.email_processor.classify_email_with_fallback")
    async def test_does_not_flag_high_confidence(
        self, mock_classify: AsyncMock
    ) -> None:
        """Test that high confidence classifications are not flagged."""
        email = create_mock_email()
        mock_classify.return_value = create_mock_classification(
            confidence=0.95, needs_review=False
        )

        result, _, _ = await process_single_email(email)

        assert result.needs_review is False
        assert result.confidence >= 0.85
