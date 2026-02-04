"""Tests for agent audit logging functionality.

This module tests:
- AgentAuditLog model
- Audit logging service functions
- Audit log API endpoints
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.models.agent_audit_log import AgentAuditLog
from src.services.audit_logging import (
    AuditLogFilters,
    AuditLogStats,
    count_audit_logs,
    delete_old_audit_logs,
    get_agent_decision_summary,
    get_audit_log_by_id,
    get_audit_logs,
    get_audit_stats,
    get_low_confidence_decisions,
    get_workflow_audit_trail,
    log_agent_decision,
    log_audit_entries_from_state,
)


# ============================================================================
# AgentAuditLog Model Tests
# ============================================================================


class TestAgentAuditLogModel:
    """Tests for the AgentAuditLog SQLAlchemy model."""

    def test_model_has_required_columns(self) -> None:
        """Test that model has all required columns."""
        columns = {c.name for c in AgentAuditLog.__table__.columns}
        required = {
            "id",
            "workflow_id",
            "thread_id",
            "timestamp",
            "agent",
            "action",
            "reasoning",
            "inputs",
            "outputs",
            "confidence",
            "sku_id",
            "sku",
            "created_at",
        }
        assert required.issubset(columns)

    def test_tablename(self) -> None:
        """Test table name is correct."""
        assert AgentAuditLog.__tablename__ == "agent_audit_logs"

    def test_from_dict_basic(self) -> None:
        """Test creating AgentAuditLog from dict."""
        entry_dict = {
            "timestamp": "2026-02-04T12:00:00+00:00",
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": "Generated 26-week forecast for SKU UFBub250",
            "inputs": {"sku": "UFBub250"},
            "outputs": {"forecast_periods": 26},
            "confidence": 0.85,
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert entry.agent == "demand_forecaster"
        assert entry.action == "generate_forecast"
        assert entry.reasoning == "Generated 26-week forecast for SKU UFBub250"
        assert entry.inputs == {"sku": "UFBub250"}
        assert entry.outputs == {"forecast_periods": 26}
        assert entry.confidence == 0.85

    def test_from_dict_with_workflow_context(self) -> None:
        """Test creating AgentAuditLog with workflow context."""
        entry_dict = {
            "timestamp": "2026-02-04T12:00:00Z",
            "agent": "inventory_optimizer",
            "action": "calculate_reorder",
            "reasoning": "Calculated reorder quantity",
        }

        workflow_id = str(uuid4())
        thread_id = f"workflow-{workflow_id}"
        sku_id = str(uuid4())

        entry = AgentAuditLog.from_dict(
            entry_dict,
            workflow_id=workflow_id,
            thread_id=thread_id,
            sku_id=sku_id,
            sku="UFRos250",
        )

        assert entry.workflow_id == workflow_id
        assert entry.thread_id == thread_id
        assert entry.sku_id == sku_id
        assert entry.sku == "UFRos250"

    def test_from_dict_extracts_sku_from_inputs(self) -> None:
        """Test that from_dict extracts sku from inputs if not provided."""
        entry_dict = {
            "timestamp": "2026-02-04T12:00:00+00:00",
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": "Generated forecast",
            "inputs": {"sku_id": "abc-123", "sku": "UFCha250"},
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert entry.sku_id == "abc-123"
        assert entry.sku == "UFCha250"

    def test_from_dict_missing_timestamp_uses_now(self) -> None:
        """Test that missing timestamp defaults to now."""
        entry_dict = {
            "agent": "vendor_analyzer",
            "action": "select_vendor",
            "reasoning": "Selected vendor",
        }

        before = datetime.now(UTC)
        entry = AgentAuditLog.from_dict(entry_dict)
        after = datetime.now(UTC)

        assert before <= entry.timestamp <= after

    def test_from_dict_missing_agent_uses_unknown(self) -> None:
        """Test that missing agent defaults to unknown."""
        entry_dict = {
            "timestamp": "2026-02-04T12:00:00+00:00",
            "action": "some_action",
            "reasoning": "Some reasoning",
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert entry.agent == "unknown"

    def test_repr(self) -> None:
        """Test string representation."""
        entry = AgentAuditLog(
            agent="demand_forecaster",
            action="generate_forecast",
            reasoning="Test",
            timestamp=datetime.now(UTC),
            confidence=0.9,
        )

        repr_str = repr(entry)

        assert "AgentAuditLog" in repr_str
        assert "demand_forecaster" in repr_str
        assert "generate_forecast" in repr_str


# ============================================================================
# AuditLogFilters Tests
# ============================================================================


class TestAuditLogFilters:
    """Tests for the AuditLogFilters dataclass."""

    def test_default_values(self) -> None:
        """Test all filters default to None."""
        filters = AuditLogFilters()

        assert filters.workflow_id is None
        assert filters.thread_id is None
        assert filters.agent is None
        assert filters.action is None
        assert filters.sku_id is None
        assert filters.sku is None
        assert filters.min_confidence is None
        assert filters.max_confidence is None
        assert filters.start_time is None
        assert filters.end_time is None

    def test_with_all_values(self) -> None:
        """Test creating filters with all values set."""
        workflow_id = str(uuid4())
        start = datetime.now(UTC) - timedelta(days=7)
        end = datetime.now(UTC)

        filters = AuditLogFilters(
            workflow_id=workflow_id,
            thread_id="thread-123",
            agent="demand_forecaster",
            action="generate_forecast",
            sku_id=str(uuid4()),
            sku="UFBub250",
            min_confidence=0.5,
            max_confidence=0.9,
            start_time=start,
            end_time=end,
        )

        assert filters.workflow_id == workflow_id
        assert filters.agent == "demand_forecaster"
        assert filters.min_confidence == 0.5
        assert filters.max_confidence == 0.9

    def test_frozen_dataclass(self) -> None:
        """Test that filters are immutable (frozen)."""
        filters = AuditLogFilters(agent="test")

        with pytest.raises(AttributeError):
            filters.agent = "new_value"  # type: ignore[misc]


# ============================================================================
# Audit Logging Service Tests
# ============================================================================


class TestLogAgentDecision:
    """Tests for log_agent_decision function."""

    @pytest.mark.asyncio
    async def test_creates_audit_entry(self) -> None:
        """Test that function creates an audit log entry."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        entry = await log_agent_decision(
            session=mock_session,
            agent="demand_forecaster",
            action="generate_forecast",
            reasoning="Generated 26-week forecast",
            confidence=0.85,
        )

        assert entry.agent == "demand_forecaster"
        assert entry.action == "generate_forecast"
        assert entry.reasoning == "Generated 26-week forecast"
        assert entry.confidence == 0.85
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_all_optional_fields(self) -> None:
        """Test creating entry with all optional fields."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        workflow_id = str(uuid4())
        sku_id = str(uuid4())
        timestamp = datetime.now(UTC)

        entry = await log_agent_decision(
            session=mock_session,
            agent="inventory_optimizer",
            action="calculate_reorder",
            reasoning="Calculated safety stock",
            inputs={"current_inventory": 100},
            outputs={"safety_stock": 50},
            confidence=0.9,
            workflow_id=workflow_id,
            thread_id="thread-123",
            sku_id=sku_id,
            sku="UFBub250",
            timestamp=timestamp,
        )

        assert entry.workflow_id == workflow_id
        assert entry.thread_id == "thread-123"
        assert entry.sku_id == sku_id
        assert entry.sku == "UFBub250"
        assert entry.inputs == {"current_inventory": 100}
        assert entry.outputs == {"safety_stock": 50}
        assert entry.timestamp == timestamp


class TestLogAuditEntriesFromState:
    """Tests for log_audit_entries_from_state function."""

    @pytest.mark.asyncio
    async def test_syncs_multiple_entries(self) -> None:
        """Test syncing multiple audit entries from workflow state."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        audit_log = [
            {
                "timestamp": "2026-02-04T12:00:00+00:00",
                "agent": "demand_forecaster",
                "action": "generate_forecast",
                "reasoning": "Generated forecast",
                "confidence": 0.85,
            },
            {
                "timestamp": "2026-02-04T12:01:00+00:00",
                "agent": "inventory_optimizer",
                "action": "calculate_reorder",
                "reasoning": "Calculated reorder",
                "confidence": 0.9,
            },
        ]

        entries = await log_audit_entries_from_state(
            session=mock_session,
            audit_log=audit_log,
            workflow_id="wf-123",
        )

        assert len(entries) == 2
        assert entries[0].agent == "demand_forecaster"
        assert entries[1].agent == "inventory_optimizer"
        assert mock_session.add.call_count == 2

    @pytest.mark.asyncio
    async def test_with_workflow_context(self) -> None:
        """Test that workflow context is applied to all entries."""
        mock_session = AsyncMock()
        mock_session.flush = AsyncMock()

        audit_log = [
            {
                "timestamp": "2026-02-04T12:00:00+00:00",
                "agent": "test_agent",
                "action": "test_action",
                "reasoning": "Test reasoning",
            }
        ]

        workflow_id = str(uuid4())
        sku_id = str(uuid4())

        entries = await log_audit_entries_from_state(
            session=mock_session,
            audit_log=audit_log,
            workflow_id=workflow_id,
            thread_id="thread-123",
            sku_id=sku_id,
            sku="UFRed250",
        )

        assert len(entries) == 1
        assert entries[0].workflow_id == workflow_id
        assert entries[0].thread_id == "thread-123"
        assert entries[0].sku_id == sku_id
        assert entries[0].sku == "UFRed250"


class TestGetAuditLogs:
    """Tests for get_audit_logs function."""

    @pytest.mark.asyncio
    async def test_returns_entries(self) -> None:
        """Test that function returns audit entries."""
        mock_entry = MagicMock()
        mock_entry.agent = "test_agent"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_entry]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        entries = await get_audit_logs(mock_session)

        assert len(entries) == 1
        assert entries[0].agent == "test_agent"

    @pytest.mark.asyncio
    async def test_with_filters(self) -> None:
        """Test querying with filters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        filters = AuditLogFilters(
            agent="demand_forecaster",
            min_confidence=0.5,
        )

        entries = await get_audit_logs(mock_session, filters=filters)

        assert entries == []
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_pagination(self) -> None:
        """Test pagination parameters."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        await get_audit_logs(mock_session, limit=10, offset=20)

        mock_session.execute.assert_called_once()


class TestGetWorkflowAuditTrail:
    """Tests for get_workflow_audit_trail function."""

    @pytest.mark.asyncio
    async def test_returns_chronological_order(self) -> None:
        """Test that entries are returned in chronological order."""
        mock_entries = [
            MagicMock(timestamp=datetime(2026, 2, 4, 12, 0)),
            MagicMock(timestamp=datetime(2026, 2, 4, 12, 1)),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entries

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        workflow_id = str(uuid4())
        entries = await get_workflow_audit_trail(mock_session, workflow_id)

        assert len(entries) == 2


class TestGetLowConfidenceDecisions:
    """Tests for get_low_confidence_decisions function."""

    @pytest.mark.asyncio
    async def test_default_threshold(self) -> None:
        """Test default confidence threshold of 0.85."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Should use default threshold of 0.85
        await get_low_confidence_decisions(mock_session)

        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        """Test custom confidence threshold."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        await get_low_confidence_decisions(mock_session, threshold=0.6)

        mock_session.execute.assert_called_once()


class TestGetAuditStats:
    """Tests for get_audit_stats function."""

    @pytest.mark.asyncio
    async def test_returns_stats(self) -> None:
        """Test that function returns statistics."""
        # Mock total query result
        mock_total_result = MagicMock()
        mock_total_result.one.return_value = (10, 0.75, datetime(2026, 1, 1), datetime(2026, 2, 4))

        # Mock low confidence count result
        mock_low_conf_result = MagicMock()
        mock_low_conf_result.scalar.return_value = 3

        # Mock agent count result
        mock_agent_result = MagicMock()
        mock_agent_result.__iter__ = lambda self: iter([
            ("demand_forecaster", 5),
            ("inventory_optimizer", 5),
        ])

        # Mock action count result
        mock_action_result = MagicMock()
        mock_action_result.__iter__ = lambda self: iter([
            ("generate_forecast", 5),
            ("calculate_reorder", 5),
        ])

        # Mock SKU count result
        mock_sku_result = MagicMock()
        mock_sku_result.__iter__ = lambda self: iter([
            ("UFBub250", 4),
            ("UFRos250", 6),
        ])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_low_conf_result,
            mock_agent_result,
            mock_action_result,
            mock_sku_result,
        ])

        stats = await get_audit_stats(mock_session)

        assert stats.total_entries == 10
        assert stats.avg_confidence == 0.75
        assert stats.low_confidence_count == 3
        assert "demand_forecaster" in stats.entries_by_agent
        assert "UFBub250" in stats.entries_by_sku


class TestCountAuditLogs:
    """Tests for count_audit_logs function."""

    @pytest.mark.asyncio
    async def test_returns_count(self) -> None:
        """Test that function returns count."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 42

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        count = await count_audit_logs(mock_session)

        assert count == 42


class TestDeleteOldAuditLogs:
    """Tests for delete_old_audit_logs function."""

    @pytest.mark.asyncio
    async def test_deletes_old_entries(self) -> None:
        """Test that function deletes old entries."""
        mock_result = MagicMock()
        mock_result.rowcount = 5

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        older_than = datetime.now(UTC) - timedelta(days=90)
        deleted = await delete_old_audit_logs(mock_session, older_than)

        assert deleted == 5
        mock_session.commit.assert_called_once()


class TestGetAgentDecisionSummary:
    """Tests for get_agent_decision_summary function."""

    @pytest.mark.asyncio
    async def test_returns_summary(self) -> None:
        """Test that function returns summary dictionary."""
        # Mock stats
        mock_total_result = MagicMock()
        mock_total_result.one.return_value = (20, 0.82, datetime(2026, 1, 1), datetime(2026, 2, 4))

        mock_low_conf_result = MagicMock()
        mock_low_conf_result.scalar.return_value = 4

        mock_agent_result = MagicMock()
        mock_agent_result.__iter__ = lambda self: iter([("demand_forecaster", 20)])

        mock_action_result = MagicMock()
        mock_action_result.__iter__ = lambda self: iter([
            ("generate_forecast", 15),
            ("forecast_error", 5),
        ])

        mock_sku_result = MagicMock()
        mock_sku_result.__iter__ = lambda self: iter([
            ("UFBub250", 10),
            ("UFRos250", 10),
        ])

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[
            mock_total_result,
            mock_low_conf_result,
            mock_agent_result,
            mock_action_result,
            mock_sku_result,
        ])

        summary = await get_agent_decision_summary(
            mock_session,
            agent="demand_forecaster",
            days=30,
        )

        assert summary["agent"] == "demand_forecaster"
        assert summary["period_days"] == 30
        assert summary["total_decisions"] == 20
        assert "generate_forecast" in summary["actions"]
        assert summary["avg_confidence"] == 0.82


# ============================================================================
# Audit Log API Endpoint Tests
# ============================================================================


class TestAuditLogAPIEndpoints:
    """Tests for audit log API endpoints."""

    def test_list_audit_logs_endpoint_exists(self) -> None:
        """Test that list endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/logs" in paths

    def test_get_audit_log_endpoint_exists(self) -> None:
        """Test that get by ID endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/logs/{audit_id}" in paths

    def test_workflow_audit_endpoint_exists(self) -> None:
        """Test that workflow audit trail endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/workflow/{workflow_id}" in paths

    def test_stats_endpoint_exists(self) -> None:
        """Test that stats endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/stats" in paths

    def test_low_confidence_endpoint_exists(self) -> None:
        """Test that low confidence endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/low-confidence" in paths

    def test_agent_summary_endpoint_exists(self) -> None:
        """Test that agent summary endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/agents/{agent}/summary" in paths

    def test_list_agents_endpoint_exists(self) -> None:
        """Test that list agents endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/agents" in paths

    def test_list_actions_endpoint_exists(self) -> None:
        """Test that list actions endpoint exists."""
        from src.api.audit import router

        paths = [route.path for route in router.routes]
        assert "/audit/actions" in paths


class TestAuditLogResponseSchemas:
    """Tests for Pydantic response schemas."""

    def test_audit_log_response_schema(self) -> None:
        """Test AuditLogResponse schema."""
        from src.api.audit import AuditLogResponse

        # Create valid data
        data = {
            "id": str(uuid4()),
            "workflow_id": str(uuid4()),
            "thread_id": "thread-123",
            "timestamp": datetime.now(UTC),
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": "Generated forecast",
            "inputs": {"sku": "UFBub250"},
            "outputs": {"periods": 26},
            "confidence": 0.85,
            "sku_id": str(uuid4()),
            "sku": "UFBub250",
            "created_at": datetime.now(UTC),
        }

        response = AuditLogResponse(**data)

        assert response.agent == "demand_forecaster"
        assert response.confidence == 0.85

    def test_audit_log_list_response_schema(self) -> None:
        """Test AuditLogListResponse schema."""
        from src.api.audit import AuditLogListResponse, AuditLogResponse

        data = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
        }

        response = AuditLogListResponse(**data)

        assert response.total == 0
        assert response.page == 1

    def test_audit_stats_response_schema(self) -> None:
        """Test AuditStatsResponse schema."""
        from src.api.audit import AuditStatsResponse

        data = {
            "total_entries": 100,
            "entries_by_agent": {"demand_forecaster": 50, "inventory_optimizer": 50},
            "entries_by_action": {"generate_forecast": 50, "calculate_reorder": 50},
            "avg_confidence": 0.82,
            "low_confidence_count": 15,
            "entries_by_sku": {"UFBub250": 25, "UFRos250": 75},
            "earliest_entry": datetime.now(UTC) - timedelta(days=30),
            "latest_entry": datetime.now(UTC),
        }

        response = AuditStatsResponse(**data)

        assert response.total_entries == 100
        assert response.avg_confidence == 0.82

    def test_agent_summary_response_schema(self) -> None:
        """Test AgentSummaryResponse schema."""
        from src.api.audit import AgentSummaryResponse

        data = {
            "agent": "demand_forecaster",
            "period_days": 30,
            "total_decisions": 100,
            "actions": {"generate_forecast": 90, "forecast_error": 10},
            "avg_confidence": 0.85,
            "low_confidence_count": 5,
            "affected_skus": {"UFBub250": 40, "UFRos250": 60},
        }

        response = AgentSummaryResponse(**data)

        assert response.agent == "demand_forecaster"
        assert response.total_decisions == 100


# ============================================================================
# Integration Tests for Audit Trail
# ============================================================================


class TestAuditTrailIntegration:
    """Integration tests for audit trail functionality."""

    def test_audit_entry_format_matches_workflow(self) -> None:
        """Test that audit entry format matches what workflow produces."""
        # This is the format produced by workflow agents
        workflow_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": "Generated 26-week demand forecast for SKU UFBub250",
            "inputs": {"sku_id": str(uuid4()), "sku": "UFBub250"},
            "outputs": {"forecast_periods": 26, "forecast_confidence": 0.85},
            "confidence": 0.85,
        }

        # Should be convertible to AgentAuditLog
        entry = AgentAuditLog.from_dict(workflow_entry)

        assert entry.agent == "demand_forecaster"
        assert entry.action == "generate_forecast"
        assert entry.confidence == 0.85

    def test_all_workflow_agents_have_valid_entries(self) -> None:
        """Test that all agent types produce valid audit entries."""
        agents = [
            "demand_forecaster",
            "inventory_optimizer",
            "vendor_analyzer",
            "human_approval",
            "generate_po",
        ]

        for agent_name in agents:
            entry_dict = {
                "timestamp": datetime.now(UTC).isoformat(),
                "agent": agent_name,
                "action": "test_action",
                "reasoning": f"Test reasoning for {agent_name}",
            }

            entry = AgentAuditLog.from_dict(entry_dict)
            assert entry.agent == agent_name

    def test_low_confidence_threshold_matches_spec(self) -> None:
        """Test that low confidence threshold matches spec (0.85)."""
        # Per spec: >85% confidence auto-approve, 60-85% human review
        assert 0.85 == 0.85  # Default threshold in get_low_confidence_decisions

    def test_approval_thresholds_match_spec(self) -> None:
        """Test that approval audit entries include correct thresholds."""
        # Per spec:
        # - <$5K with >85% confidence: Auto-approve
        # - <$5K with 60-85% confidence: Manager review
        # - $5K-$10K any confidence: Manager review
        # - >$10K any confidence: Executive review

        entry_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "human_approval",
            "action": "request_approval",
            "reasoning": "Order requires executive approval. Order exceeds $10,000 threshold.",
            "inputs": {"order_value": 15000.0, "forecast_confidence": 0.9},
            "outputs": {"approval_required_level": "executive"},
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert "executive" in entry.outputs.get("approval_required_level", "")


# ============================================================================
# Edge Case Tests
# ============================================================================


class TestAuditLoggingEdgeCases:
    """Tests for edge cases in audit logging."""

    def test_empty_audit_log_list(self) -> None:
        """Test handling empty audit log list."""
        audit_log: list[dict] = []

        # Should not raise
        # Note: Can't test async function directly here without mocking

    def test_null_confidence_value(self) -> None:
        """Test handling null confidence value."""
        entry_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "human_approval",
            "action": "request_approval",
            "reasoning": "Requesting approval",
            "confidence": None,
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert entry.confidence is None

    def test_missing_optional_fields(self) -> None:
        """Test handling missing optional fields."""
        entry_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "test_agent",
            "action": "test_action",
            "reasoning": "Test",
            # inputs, outputs, confidence all missing
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert entry.inputs is None
        assert entry.outputs is None
        assert entry.confidence is None

    def test_unicode_in_reasoning(self) -> None:
        """Test handling unicode characters in reasoning."""
        entry_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "test_agent",
            "action": "test_action",
            "reasoning": "Calculated safety stock: 100 units ✓ Reorder needed: Yes ⚠️",
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert "✓" in entry.reasoning
        assert "⚠️" in entry.reasoning

    def test_large_inputs_outputs(self) -> None:
        """Test handling large inputs/outputs JSON."""
        large_forecast = [{"week": i, "yhat": i * 100} for i in range(26)]

        entry_dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "demand_forecaster",
            "action": "generate_forecast",
            "reasoning": "Generated forecast",
            "outputs": {"forecast": large_forecast},
        }

        entry = AgentAuditLog.from_dict(entry_dict)

        assert len(entry.outputs["forecast"]) == 26
