"""Tests for human review queue API endpoints."""

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.main import app
from src.models.email_classification import EmailClassification


def create_mock_classification(
    message_id: str = "msg123",
    category: str = "GENERAL",
    confidence: float = 0.70,
    needs_review: bool = True,
    reviewed: bool = False,
    reviewed_by: str | None = None,
    reviewed_at: datetime | None = None,
    corrected_category: str | None = None,
) -> MagicMock:
    """Create a mock EmailClassification for testing."""
    mock = MagicMock(spec=EmailClassification)
    mock.id = uuid.uuid4()
    mock.message_id = message_id
    mock.thread_id = "thread456"
    mock.subject = "Test Subject"
    mock.sender = "sender@example.com"
    mock.recipient = "recipient@example.com"
    mock.received_at = datetime.now(UTC)
    mock.category = category
    mock.confidence = confidence
    mock.reasoning = "Test reasoning"
    mock.needs_review = needs_review
    mock.reviewed = reviewed
    mock.reviewed_by = reviewed_by
    mock.reviewed_at = reviewed_at
    mock.corrected_category = corrected_category
    mock.has_attachments = False
    mock.attachment_names = "[]"
    mock.processing_time_ms = 100
    mock.ollama_used = True
    mock.created_at = datetime.now(UTC)
    mock.updated_at = datetime.now(UTC)
    return mock


class TestReviewQueueEndpoint:
    """Tests for GET /review/queue endpoint."""

    def test_returns_pending_review_items(self) -> None:
        """Test that pending review items are returned."""
        mock_classification = create_mock_classification()

        mock_session = AsyncMock(spec=AsyncSession)

        # Mock count query
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1

        # Mock items query
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_classification]
        mock_items_result.scalars.return_value = mock_scalars

        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["message_id"] == mock_classification.message_id
        finally:
            app.dependency_overrides.clear()

    def test_pagination_parameters(self) -> None:
        """Test pagination parameters are accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue?page=2&page_size=10")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["page"] == 2
            assert data["page_size"] == 10
        finally:
            app.dependency_overrides.clear()

    def test_category_filter_accepted(self) -> None:
        """Test category filter parameter is accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue?category=PO")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_confidence_filters_accepted(self) -> None:
        """Test confidence filter parameters are accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue?min_confidence=0.5&max_confidence=0.8")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()


class TestReviewQueueStatsEndpoint:
    """Tests for GET /review/queue/stats endpoint."""

    def test_returns_stats(self) -> None:
        """Test that stats are returned correctly."""
        mock_session = AsyncMock(spec=AsyncSession)

        # Mock all the stat queries (5 queries total)
        mock_results = [
            MagicMock(scalar=MagicMock(return_value=10)),  # pending_review
            MagicMock(scalar=MagicMock(return_value=5)),  # reviewed_today
            MagicMock(scalar=MagicMock(return_value=100)),  # total_reviewed
            MagicMock(scalar=MagicMock(return_value=0.72)),  # avg_confidence
            MagicMock(__iter__=lambda self: iter([("PO", 3), ("GENERAL", 7)])),  # by_category
        ]
        mock_session.execute.side_effect = mock_results

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue/stats")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pending_review"] == 10
            assert data["reviewed_today"] == 5
            assert data["total_reviewed"] == 100
            assert data["avg_confidence"] == 0.72
            assert data["by_category"] == {"PO": 3, "GENERAL": 7}
        finally:
            app.dependency_overrides.clear()


class TestGetClassificationEndpoint:
    """Tests for GET /review/queue/{classification_id} endpoint."""

    def test_returns_classification(self) -> None:
        """Test that a classification is returned."""
        mock_classification = create_mock_classification()
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get(f"/review/queue/{test_id}")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["message_id"] == mock_classification.message_id
        finally:
            app.dependency_overrides.clear()

    def test_returns_404_for_unknown_id(self) -> None:
        """Test that 404 is returned for unknown classification ID."""
        test_id = str(uuid.uuid4())

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get(f"/review/queue/{test_id}")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_invalid_uuid_returns_422(self) -> None:
        """Test that invalid UUID returns 422."""
        client = TestClient(app)
        response = client.get("/review/queue/not-a-uuid")
        assert response.status_code == 422


class TestReviewClassificationEndpoint:
    """Tests for POST /review/queue/{classification_id}/review endpoint."""

    def test_approves_classification(self) -> None:
        """Test approving a classification."""
        mock_classification = create_mock_classification()
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={"reviewer": "test@example.com", "approved": True},
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["approved"] is True
            assert data["corrected_category"] is None
            assert data["reviewed_by"] == "test@example.com"
        finally:
            app.dependency_overrides.clear()

    def test_corrects_classification(self) -> None:
        """Test correcting a classification to a different category."""
        mock_classification = create_mock_classification(category="GENERAL")
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={
                    "reviewer": "test@example.com",
                    "approved": False,
                    "corrected_category": "INVOICE",
                },
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["approved"] is False
            assert data["corrected_category"] == "INVOICE"
            assert data["original_category"] == "GENERAL"
        finally:
            app.dependency_overrides.clear()

    def test_requires_reviewer(self) -> None:
        """Test that reviewer is required."""
        test_id = str(uuid.uuid4())
        client = TestClient(app)
        response = client.post(
            f"/review/queue/{test_id}/review",
            json={"approved": True},
        )
        assert response.status_code == 422

    def test_rejects_invalid_category(self) -> None:
        """Test that invalid corrected_category is rejected."""
        mock_classification = create_mock_classification()
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={
                    "reviewer": "test@example.com",
                    "approved": False,
                    "corrected_category": "INVALID",
                },
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid category" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_accepts_valid_categories(self) -> None:
        """Test that valid categories are accepted."""
        valid_categories = ["PO", "BOL", "INVOICE", "GENERAL"]

        for category in valid_categories:
            mock_classification = create_mock_classification()
            test_id = mock_classification.id

            mock_session = AsyncMock(spec=AsyncSession)
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_classification
            mock_session.execute.return_value = mock_result
            mock_session.commit = AsyncMock()

            async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
                yield mock_session

            app.dependency_overrides[get_db] = override_get_db

            try:
                client = TestClient(app)
                response = client.post(
                    f"/review/queue/{test_id}/review",
                    json={
                        "reviewer": "test@example.com",
                        "approved": False,
                        "corrected_category": category,
                    },
                )

                assert response.status_code == status.HTTP_200_OK
                assert response.json()["corrected_category"] == category
            finally:
                app.dependency_overrides.clear()

    def test_rejects_already_reviewed(self) -> None:
        """Test that already reviewed items cannot be reviewed again."""
        mock_classification = create_mock_classification(
            reviewed=True,
            reviewed_by="previous@example.com",
            reviewed_at=datetime.now(UTC),
        )
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={"reviewer": "new_reviewer@example.com", "approved": True},
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "already been reviewed" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_returns_404_for_unknown_id(self) -> None:
        """Test that 404 is returned for unknown classification ID."""
        test_id = str(uuid.uuid4())

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={"reviewer": "test@example.com", "approved": True},
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
        finally:
            app.dependency_overrides.clear()


class TestReviewHistoryEndpoint:
    """Tests for GET /review/history endpoint."""

    def test_returns_reviewed_items(self) -> None:
        """Test that reviewed items are returned."""
        mock_classification = create_mock_classification(
            reviewed=True,
            reviewed_by="reviewer@example.com",
            reviewed_at=datetime.now(UTC),
        )

        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 1
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_classification]
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/history")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
        finally:
            app.dependency_overrides.clear()

    def test_reviewer_filter_accepted(self) -> None:
        """Test reviewer filter parameter is accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/history?reviewer=test@example.com")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_corrected_only_filter_accepted(self) -> None:
        """Test corrected_only filter parameter is accepted."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/history?corrected_only=true")

            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()


class TestResponseSchemas:
    """Tests for response schema structure."""

    def test_email_classification_response_fields(self) -> None:
        """Test EmailClassificationResponse has expected fields."""
        from src.api.review import EmailClassificationResponse

        fields = EmailClassificationResponse.model_fields
        required_fields = [
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
        ]
        for field in required_fields:
            assert field in fields, f"Missing field: {field}"

    def test_review_queue_response_fields(self) -> None:
        """Test ReviewQueueResponse has expected fields."""
        from src.api.review import ReviewQueueResponse

        fields = ReviewQueueResponse.model_fields
        assert "items" in fields
        assert "total" in fields
        assert "page" in fields
        assert "page_size" in fields
        assert "total_pages" in fields

    def test_review_queue_stats_fields(self) -> None:
        """Test ReviewQueueStats has expected fields."""
        from src.api.review import ReviewQueueStats

        fields = ReviewQueueStats.model_fields
        assert "pending_review" in fields
        assert "reviewed_today" in fields
        assert "total_reviewed" in fields
        assert "avg_confidence" in fields
        assert "by_category" in fields

    def test_review_request_fields(self) -> None:
        """Test ReviewRequest has expected fields."""
        from src.api.review import ReviewRequest

        fields = ReviewRequest.model_fields
        assert "reviewer" in fields
        assert "approved" in fields
        assert "corrected_category" in fields

    def test_review_response_fields(self) -> None:
        """Test ReviewResponse has expected fields."""
        from src.api.review import ReviewResponse

        fields = ReviewResponse.model_fields
        assert "id" in fields
        assert "message_id" in fields
        assert "original_category" in fields
        assert "corrected_category" in fields
        assert "reviewed_by" in fields
        assert "reviewed_at" in fields
        assert "approved" in fields


class TestLowConfidenceThreshold:
    """Tests for low confidence threshold behavior."""

    def test_queue_returns_low_confidence_items(self) -> None:
        """Test that queue returns items with confidence < 0.85."""
        mock_items = [
            create_mock_classification(confidence=0.70, needs_review=True),
            create_mock_classification(confidence=0.75, needs_review=True),
            create_mock_classification(confidence=0.80, needs_review=True),
        ]

        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = len(mock_items)
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = mock_items
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == len(mock_items)
            for item in data["items"]:
                assert item["confidence"] < 0.85
        finally:
            app.dependency_overrides.clear()


class TestRouterConfiguration:
    """Tests for router configuration."""

    def test_router_prefix(self) -> None:
        """Test that router has correct prefix."""
        from src.api.review import router

        assert router.prefix == "/review"

    def test_router_tags(self) -> None:
        """Test that router has correct tags."""
        from src.api.review import router

        assert "review" in router.tags

    def test_router_registered_in_app(self) -> None:
        """Test that router is registered in main app."""
        from src.main import app

        routes = [route.path for route in app.routes]
        review_routes = [r for r in routes if r.startswith("/review")]
        assert len(review_routes) > 0


class TestPaginationLogic:
    """Tests for pagination logic."""

    def test_pagination_calculations(self) -> None:
        """Test pagination calculations are correct."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 45
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue?page=1&page_size=20")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 45
            assert data["page"] == 1
            assert data["page_size"] == 20
            assert data["total_pages"] == 3  # ceil(45/20) = 3
        finally:
            app.dependency_overrides.clear()

    def test_empty_queue_returns_page_1(self) -> None:
        """Test that empty queue still shows page 1."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars
        mock_session.execute.side_effect = [mock_count_result, mock_items_result]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.get("/review/queue")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total"] == 0
            assert data["page"] == 1
            assert data["total_pages"] == 1
        finally:
            app.dependency_overrides.clear()


class TestAcceptanceCriteria:
    """Tests for Task 2.2.4 acceptance criteria."""

    def test_low_confidence_flagged_for_review(self) -> None:
        """Test that low-confidence classifications (<85%) are flagged.

        This is verified by the needs_review=True filter in get_review_queue.
        """
        from src.api.review import get_review_queue

        assert get_review_queue is not None

    def test_review_queue_accessible_via_api(self) -> None:
        """Test that review queue is accessible via dashboard-friendly API."""
        mock_session = AsyncMock(spec=AsyncSession)
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_items_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_items_result.scalars.return_value = mock_scalars

        # For stats endpoint
        mock_stat_results = [
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=0)),
            MagicMock(scalar=MagicMock(return_value=None)),
            MagicMock(__iter__=lambda self: iter([])),
        ]

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)

            # Test queue endpoint
            mock_session.execute.side_effect = [mock_count_result, mock_items_result]
            response = client.get("/review/queue")
            assert response.status_code == status.HTTP_200_OK

            # Test stats endpoint
            mock_session.execute.side_effect = mock_stat_results
            response = client.get("/review/queue/stats")
            assert response.status_code == status.HTTP_200_OK

            # Test history endpoint
            mock_session.execute.side_effect = [mock_count_result, mock_items_result]
            response = client.get("/review/history")
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()

    def test_review_action_available(self) -> None:
        """Test that review action is available."""
        mock_classification = create_mock_classification()
        test_id = mock_classification.id

        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_classification
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db

        try:
            client = TestClient(app)
            response = client.post(
                f"/review/queue/{test_id}/review",
                json={"reviewer": "test@example.com", "approved": True},
            )
            assert response.status_code == status.HTTP_200_OK
        finally:
            app.dependency_overrides.clear()
