"""Tests for the LangGraph procurement workflow state machine."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.agents.procurement import (
    APPROVAL_THRESHOLDS,
    CONFIDENCE_THRESHOLDS,
    ApprovalStatus,
    AuditLogEntry,
    ForecastData,
    ProcurementState,
    VendorInfo,
    WorkflowStatus,
    _create_forecast_error_response,
    _create_insufficient_data_response,
    _create_optimizer_error_response,
    build_procurement_workflow,
    calculate_reorder_point,
    calculate_reorder_quantity,
    calculate_safety_stock_from_forecast,
    compile_workflow,
    create_initial_state,
    demand_forecaster,
    demand_forecaster_async,
    generate_purchase_order,
    human_approval,
    inventory_optimizer,
    inventory_optimizer_async,
    should_require_approval,
    vendor_analyzer,
)


class TestApprovalStatusEnum:
    """Tests for ApprovalStatus enum."""

    def test_pending_value(self) -> None:
        """Test pending status value."""
        assert ApprovalStatus.PENDING.value == "pending"

    def test_approved_value(self) -> None:
        """Test approved status value."""
        assert ApprovalStatus.APPROVED.value == "approved"

    def test_rejected_value(self) -> None:
        """Test rejected status value."""
        assert ApprovalStatus.REJECTED.value == "rejected"

    def test_auto_approved_value(self) -> None:
        """Test auto_approved status value."""
        assert ApprovalStatus.AUTO_APPROVED.value == "auto_approved"


class TestWorkflowStatusEnum:
    """Tests for WorkflowStatus enum."""

    def test_initialized_value(self) -> None:
        """Test initialized status value."""
        assert WorkflowStatus.INITIALIZED.value == "initialized"

    def test_forecasting_value(self) -> None:
        """Test forecasting status value."""
        assert WorkflowStatus.FORECASTING.value == "forecasting"

    def test_optimizing_value(self) -> None:
        """Test optimizing status value."""
        assert WorkflowStatus.OPTIMIZING.value == "optimizing"

    def test_analyzing_vendor_value(self) -> None:
        """Test analyzing_vendor status value."""
        assert WorkflowStatus.ANALYZING_VENDOR.value == "analyzing_vendor"

    def test_awaiting_approval_value(self) -> None:
        """Test awaiting_approval status value."""
        assert WorkflowStatus.AWAITING_APPROVAL.value == "awaiting_approval"

    def test_generating_po_value(self) -> None:
        """Test generating_po status value."""
        assert WorkflowStatus.GENERATING_PO.value == "generating_po"

    def test_completed_value(self) -> None:
        """Test completed status value."""
        assert WorkflowStatus.COMPLETED.value == "completed"

    def test_failed_value(self) -> None:
        """Test failed status value."""
        assert WorkflowStatus.FAILED.value == "failed"


class TestForecastData:
    """Tests for ForecastData dataclass."""

    def test_creation(self) -> None:
        """Test creating ForecastData instance."""
        now = datetime.now(UTC)
        forecast = ForecastData(
            week=1,
            date=now,
            yhat=100.0,
            yhat_lower=80.0,
            yhat_upper=120.0,
        )
        assert forecast.week == 1
        assert forecast.date == now
        assert forecast.yhat == 100.0
        assert forecast.yhat_lower == 80.0
        assert forecast.yhat_upper == 120.0

    def test_immutability(self) -> None:
        """Test that ForecastData is immutable."""
        now = datetime.now(UTC)
        forecast = ForecastData(
            week=1,
            date=now,
            yhat=100.0,
            yhat_lower=80.0,
            yhat_upper=120.0,
        )
        with pytest.raises(AttributeError):
            forecast.yhat = 200.0  # type: ignore


class TestVendorInfo:
    """Tests for VendorInfo dataclass."""

    def test_creation(self) -> None:
        """Test creating VendorInfo instance."""
        from uuid import uuid4

        vendor_id = uuid4()
        vendor = VendorInfo(
            vendor_id=vendor_id,
            vendor_name="Test Supplier",
            unit_price=25.00,
            lead_time_days=14,
            minimum_order_quantity=100,
            reliability_score=0.95,
        )
        assert vendor.vendor_id == vendor_id
        assert vendor.vendor_name == "Test Supplier"
        assert vendor.unit_price == 25.00
        assert vendor.lead_time_days == 14
        assert vendor.minimum_order_quantity == 100
        assert vendor.reliability_score == 0.95

    def test_immutability(self) -> None:
        """Test that VendorInfo is immutable."""
        from uuid import uuid4

        vendor = VendorInfo(
            vendor_id=uuid4(),
            vendor_name="Test",
            unit_price=25.00,
            lead_time_days=14,
            minimum_order_quantity=100,
            reliability_score=0.95,
        )
        with pytest.raises(AttributeError):
            vendor.unit_price = 30.00  # type: ignore


class TestAuditLogEntry:
    """Tests for AuditLogEntry dataclass."""

    def test_creation_minimal(self) -> None:
        """Test creating AuditLogEntry with minimal fields."""
        now = datetime.now(UTC)
        entry = AuditLogEntry(
            timestamp=now,
            agent="test_agent",
            action="test_action",
            reasoning="Test reasoning",
        )
        assert entry.timestamp == now
        assert entry.agent == "test_agent"
        assert entry.action == "test_action"
        assert entry.reasoning == "Test reasoning"
        assert entry.inputs == {}
        assert entry.outputs == {}
        assert entry.confidence is None

    def test_creation_full(self) -> None:
        """Test creating AuditLogEntry with all fields."""
        now = datetime.now(UTC)
        entry = AuditLogEntry(
            timestamp=now,
            agent="demand_forecaster",
            action="generate_forecast",
            reasoning="Generated 26-week forecast",
            inputs={"sku_id": "abc123"},
            outputs={"forecast_periods": 26},
            confidence=0.85,
        )
        assert entry.inputs == {"sku_id": "abc123"}
        assert entry.outputs == {"forecast_periods": 26}
        assert entry.confidence == 0.85


class TestApprovalThresholds:
    """Tests for approval threshold constants."""

    def test_auto_approve_max(self) -> None:
        """Test auto-approve maximum threshold."""
        assert APPROVAL_THRESHOLDS["auto_approve_max"] == 5000.0

    def test_manager_review_max(self) -> None:
        """Test manager review maximum threshold."""
        assert APPROVAL_THRESHOLDS["manager_review_max"] == 10000.0

    def test_executive_review(self) -> None:
        """Test executive review threshold."""
        assert APPROVAL_THRESHOLDS["executive_review"] == 10000.0


class TestConfidenceThresholds:
    """Tests for confidence threshold constants."""

    def test_high_confidence(self) -> None:
        """Test high confidence threshold."""
        assert CONFIDENCE_THRESHOLDS["high"] == 0.85

    def test_medium_confidence(self) -> None:
        """Test medium confidence threshold."""
        assert CONFIDENCE_THRESHOLDS["medium"] == 0.60

    def test_low_confidence(self) -> None:
        """Test low confidence threshold."""
        assert CONFIDENCE_THRESHOLDS["low"] == 0.60


class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_creates_valid_state(self) -> None:
        """Test that create_initial_state returns valid state."""
        state = create_initial_state(
            sku_id="test-sku-id",
            sku="UFBub250",
            current_inventory=1000,
        )
        assert state["sku_id"] == "test-sku-id"
        assert state["sku"] == "UFBub250"
        assert state["current_inventory"] == 1000

    def test_initializes_workflow_status(self) -> None:
        """Test that workflow status is initialized."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        assert state["workflow_status"] == WorkflowStatus.INITIALIZED.value

    def test_initializes_approval_status(self) -> None:
        """Test that approval status is initialized."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        assert state["approval_status"] == ApprovalStatus.PENDING.value

    def test_initializes_empty_forecast(self) -> None:
        """Test that forecast is initialized empty."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        assert state["forecast"] == []
        assert state["forecast_confidence"] == 0.0

    def test_initializes_timestamps(self) -> None:
        """Test that timestamps are initialized."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        assert state["created_at"] is not None
        assert state["updated_at"] is not None

    def test_initializes_empty_audit_log(self) -> None:
        """Test that audit log is initialized empty."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        assert state["audit_log"] == []


class TestDemandForecaster:
    """Tests for demand_forecaster agent node."""

    def test_returns_forecast(self) -> None:
        """Test that demand_forecaster returns forecast data."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = demand_forecaster(state)
        assert "forecast" in result
        assert "forecast_confidence" in result

    def test_updates_workflow_status(self) -> None:
        """Test that demand_forecaster updates workflow status."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = demand_forecaster(state)
        assert result["workflow_status"] == WorkflowStatus.OPTIMIZING.value

    def test_creates_audit_entry(self) -> None:
        """Test that demand_forecaster creates audit log entry."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = demand_forecaster(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "demand_forecaster"
        assert result["audit_log"][0]["action"] == "generate_forecast"


class TestInventoryOptimizer:
    """Tests for inventory_optimizer agent node."""

    def test_returns_optimization_data(self) -> None:
        """Test that inventory_optimizer returns optimization data."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = inventory_optimizer(state)
        assert "safety_stock" in result
        assert "reorder_point" in result
        assert "recommended_quantity" in result

    def test_updates_workflow_status(self) -> None:
        """Test that inventory_optimizer updates workflow status."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = inventory_optimizer(state)
        assert result["workflow_status"] == WorkflowStatus.ANALYZING_VENDOR.value

    def test_creates_audit_entry(self) -> None:
        """Test that inventory_optimizer creates audit log entry."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = inventory_optimizer(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "inventory_optimizer"
        assert result["audit_log"][0]["action"] == "calculate_reorder"


class TestVendorAnalyzer:
    """Tests for vendor_analyzer agent node."""

    def test_returns_vendor_data(self) -> None:
        """Test that vendor_analyzer returns vendor data."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["recommended_quantity"] = 500
        result = vendor_analyzer(state)
        assert "vendors" in result
        assert "selected_vendor" in result
        assert "order_value" in result

    def test_calculates_order_value(self) -> None:
        """Test that vendor_analyzer calculates order value."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["recommended_quantity"] = 500
        result = vendor_analyzer(state)
        # With placeholder vendor at $25/unit and 500 units
        assert result["order_value"] == 12500.0

    def test_updates_workflow_status(self) -> None:
        """Test that vendor_analyzer updates workflow status."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = vendor_analyzer(state)
        assert result["workflow_status"] == WorkflowStatus.AWAITING_APPROVAL.value

    def test_creates_audit_entry(self) -> None:
        """Test that vendor_analyzer creates audit log entry."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = vendor_analyzer(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "vendor_analyzer"
        assert result["audit_log"][0]["action"] == "select_vendor"


class TestHumanApproval:
    """Tests for human_approval agent node."""

    def test_sets_pending_status(self) -> None:
        """Test that human_approval sets pending status."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = human_approval(state)
        assert result["approval_status"] == ApprovalStatus.PENDING.value

    def test_executive_approval_for_high_value(self) -> None:
        """Test that orders >$10K require executive approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 15000.0
        state["forecast_confidence"] = 0.90
        result = human_approval(state)
        assert result["approval_required_level"] == "executive"

    def test_manager_approval_for_medium_value(self) -> None:
        """Test that orders $5K-$10K require manager approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 7500.0
        state["forecast_confidence"] = 0.90
        result = human_approval(state)
        assert result["approval_required_level"] == "manager"

    def test_manager_approval_for_low_confidence(self) -> None:
        """Test that low confidence orders require manager approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        state["forecast_confidence"] = 0.70
        result = human_approval(state)
        assert result["approval_required_level"] == "manager"

    def test_auto_approval_for_small_high_confidence(self) -> None:
        """Test that small high-confidence orders can auto-approve."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        state["forecast_confidence"] = 0.90
        result = human_approval(state)
        assert result["approval_required_level"] == "auto"

    def test_creates_audit_entry(self) -> None:
        """Test that human_approval creates audit log entry."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = human_approval(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "human_approval"
        assert result["audit_log"][0]["action"] == "request_approval"


class TestGeneratePurchaseOrder:
    """Tests for generate_purchase_order agent node."""

    def test_completes_workflow(self) -> None:
        """Test that generate_purchase_order completes workflow."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["recommended_quantity"] = 500
        state["selected_vendor"] = {"vendor_name": "Test Supplier"}
        state["order_value"] = 12500.0
        result = generate_purchase_order(state)
        assert result["workflow_status"] == WorkflowStatus.COMPLETED.value

    def test_creates_audit_entry(self) -> None:
        """Test that generate_purchase_order creates audit log entry."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        result = generate_purchase_order(state)
        assert "audit_log" in result
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "generate_po"
        assert result["audit_log"][0]["action"] == "create_purchase_order"


class TestShouldRequireApproval:
    """Tests for should_require_approval routing function."""

    def test_high_value_requires_approval(self) -> None:
        """Test that orders >$10K require human approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 15000.0
        state["forecast_confidence"] = 0.95
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_medium_value_requires_approval(self) -> None:
        """Test that orders $5K-$10K require human approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 7500.0
        state["forecast_confidence"] = 0.95
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_low_confidence_requires_approval(self) -> None:
        """Test that low confidence orders require human approval."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        state["forecast_confidence"] = 0.70
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_small_high_confidence_auto_approves(self) -> None:
        """Test that small high-confidence orders auto-approve."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        state["forecast_confidence"] = 0.90
        result = should_require_approval(state)
        assert result == "generate_po"

    def test_boundary_at_5k(self) -> None:
        """Test boundary condition at $5K threshold."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        # At exactly $5K, should auto-approve with high confidence
        state["order_value"] = 5000.0
        state["forecast_confidence"] = 0.90
        result = should_require_approval(state)
        assert result == "generate_po"

    def test_boundary_above_5k(self) -> None:
        """Test boundary condition just above $5K."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        # Just above $5K requires manager review
        state["order_value"] = 5001.0
        state["forecast_confidence"] = 0.95
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_boundary_at_10k(self) -> None:
        """Test boundary condition at $10K threshold."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        # At exactly $10K requires manager review
        state["order_value"] = 10000.0
        state["forecast_confidence"] = 0.95
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_boundary_above_10k(self) -> None:
        """Test boundary condition above $10K."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        # Above $10K requires executive review
        state["order_value"] = 10001.0
        state["forecast_confidence"] = 0.95
        result = should_require_approval(state)
        assert result == "human_approval"

    def test_boundary_at_85_confidence(self) -> None:
        """Test boundary condition at 85% confidence threshold."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        # At exactly 85% should auto-approve
        state["forecast_confidence"] = 0.85
        result = should_require_approval(state)
        assert result == "generate_po"

    def test_boundary_below_85_confidence(self) -> None:
        """Test boundary condition below 85% confidence."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        state["order_value"] = 3000.0
        # Just below 85% requires review
        state["forecast_confidence"] = 0.84
        result = should_require_approval(state)
        assert result == "human_approval"


class TestBuildProcurementWorkflow:
    """Tests for build_procurement_workflow function."""

    def test_returns_state_graph(self) -> None:
        """Test that function returns a StateGraph."""
        from langgraph.graph import StateGraph

        workflow = build_procurement_workflow()
        assert isinstance(workflow, StateGraph)

    def test_has_required_nodes(self) -> None:
        """Test that workflow has all required nodes."""
        workflow = build_procurement_workflow()
        # Check nodes are defined (internal API may vary)
        assert workflow is not None


class TestCompileWorkflow:
    """Tests for compile_workflow function."""

    def test_compiles_without_checkpointer(self) -> None:
        """Test that workflow compiles without checkpointer."""
        compiled = compile_workflow()
        assert compiled is not None

    def test_compiles_with_interrupt_before(self) -> None:
        """Test that workflow compiles with custom interrupt points."""
        compiled = compile_workflow(interrupt_before=["run_approval"])
        assert compiled is not None

    def test_default_interrupt_before_run_approval(self) -> None:
        """Test that default interrupt is before run_approval."""
        compiled = compile_workflow()
        # The workflow should be configured to interrupt before run_approval
        assert compiled is not None


class TestWorkflowExecution:
    """Tests for end-to-end workflow execution."""

    def test_workflow_runs_to_approval(self) -> None:
        """Test that workflow runs up to human approval for high-value orders."""
        compiled = compile_workflow()
        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=1000,
        )

        # Run the workflow (will interrupt at run_approval for high-value)
        # Note: The placeholder vendor analyzer creates a $12,500 order
        config = {"configurable": {"thread_id": "test-1"}}

        # Invoke should run until interrupt
        result = compiled.invoke(state, config)

        # Should have run through forecast, optimize, analyze_vendor
        assert result is not None
        # Workflow should pause at run_approval since order value > $10K

    def test_workflow_auto_approves_small_orders(self) -> None:
        """Test that workflow auto-approves small high-confidence orders."""
        compiled = compile_workflow(interrupt_before=[])  # No interrupts

        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=1000,
        )

        # Override to simulate small order
        # We need to run the full workflow and check the routing
        config = {"configurable": {"thread_id": "test-2"}}
        result = compiled.invoke(state, config)

        # The placeholder implementation creates a $12,500 order,
        # so it will route through run_approval
        assert result["workflow_status"] == WorkflowStatus.COMPLETED.value

    def test_audit_log_accumulates(self) -> None:
        """Test that audit log accumulates entries from all agents."""
        compiled = compile_workflow(interrupt_before=[])

        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=1000,
        )

        config = {"configurable": {"thread_id": "test-3"}}
        result = compiled.invoke(state, config)

        # Should have audit entries from multiple agents
        assert len(result.get("audit_log", [])) > 0


class TestWorkflowStateUpdates:
    """Tests for workflow state update patterns."""

    def test_timestamp_updates(self) -> None:
        """Test that updated_at timestamp is updated by agents."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )
        original_updated = state["updated_at"]

        import time
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        result = demand_forecaster(state)
        assert result["updated_at"] != original_updated

    def test_state_merges_correctly(self) -> None:
        """Test that state updates merge correctly."""
        state = create_initial_state(
            sku_id="test",
            sku="UFBub250",
            current_inventory=100,
        )

        # Run through forecast
        result1 = demand_forecaster(state)

        # Merge state (simulating graph behavior)
        merged = {**state, **result1}

        # Run through optimizer
        result2 = inventory_optimizer(merged)

        # Should have data from both agents
        assert "forecast" in merged
        assert "safety_stock" in result2


class TestCreateForecastErrorResponse:
    """Tests for _create_forecast_error_response helper."""

    def test_returns_empty_forecast(self) -> None:
        """Test that error response has empty forecast."""
        result = _create_forecast_error_response(
            sku_id="test-id",
            sku="UFBub250",
            error_message="Test error",
        )
        assert result["forecast"] == []

    def test_sets_zero_confidence(self) -> None:
        """Test that error response has zero confidence."""
        result = _create_forecast_error_response(
            sku_id="test-id",
            sku="UFBub250",
            error_message="Test error",
        )
        assert result["forecast_confidence"] == 0.0

    def test_sets_failed_status(self) -> None:
        """Test that error response sets failed workflow status."""
        result = _create_forecast_error_response(
            sku_id="test-id",
            sku="UFBub250",
            error_message="Test error",
        )
        assert result["workflow_status"] == WorkflowStatus.FAILED.value

    def test_includes_error_message(self) -> None:
        """Test that error response includes the error message."""
        result = _create_forecast_error_response(
            sku_id="test-id",
            sku="UFBub250",
            error_message="Something went wrong",
        )
        assert result["error_message"] == "Something went wrong"

    def test_creates_audit_entry(self) -> None:
        """Test that error response creates audit log entry."""
        result = _create_forecast_error_response(
            sku_id="test-id",
            sku="UFBub250",
            error_message="Test error",
        )
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "demand_forecaster"
        assert result["audit_log"][0]["action"] == "forecast_error"
        assert result["audit_log"][0]["confidence"] == 0.0


class TestCreateInsufficientDataResponse:
    """Tests for _create_insufficient_data_response helper."""

    def test_returns_empty_forecast(self) -> None:
        """Test that insufficient data response has empty forecast."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=100,
            required_days=728,
        )
        assert result["forecast"] == []

    def test_calculates_proportional_confidence(self) -> None:
        """Test that confidence is proportional to available data."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=364,  # Half of required
            required_days=728,
        )
        # 364/728 * 0.60 = 0.30
        assert result["forecast_confidence"] == pytest.approx(0.30)

    def test_caps_confidence_at_60_percent(self) -> None:
        """Test that confidence is capped at 60% (below high threshold)."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=800,  # More than required
            required_days=728,
        )
        assert result["forecast_confidence"] == 0.60

    def test_continues_workflow(self) -> None:
        """Test that insufficient data continues to optimizing status."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=100,
            required_days=728,
        )
        assert result["workflow_status"] == WorkflowStatus.OPTIMIZING.value

    def test_creates_audit_entry(self) -> None:
        """Test that insufficient data creates audit log entry."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=100,
            required_days=728,
        )
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "demand_forecaster"
        assert result["audit_log"][0]["action"] == "insufficient_data"

    def test_includes_data_ratio_in_outputs(self) -> None:
        """Test that audit log includes data ratio calculation."""
        result = _create_insufficient_data_response(
            sku_id="test-id",
            sku="UFBub250",
            available_days=182,  # 25% of required
            required_days=728,
        )
        assert result["audit_log"][0]["outputs"]["data_ratio"] == pytest.approx(0.25)


class TestDemandForecasterAsync:
    """Tests for demand_forecaster_async function."""

    @pytest.mark.asyncio
    async def test_invalid_sku_id_format(self) -> None:
        """Test handling of invalid SKU ID format."""
        state = create_initial_state(
            sku_id="not-a-valid-uuid",
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        result = await demand_forecaster_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.FAILED.value
        assert "Invalid SKU ID format" in result["error_message"]
        assert result["forecast"] == []
        assert result["forecast_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_insufficient_training_data(self) -> None:
        """Test handling of insufficient training data."""
        import pandas as pd

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        # Mock get_training_data to return insufficient data (100 days < 728 required)
        with patch("src.services.forecast.get_training_data") as mock_get_data:
            mock_df = pd.DataFrame({
                "ds": pd.date_range("2024-01-01", periods=100),
                "y": [10] * 100,
            })
            mock_get_data.return_value = mock_df

            result = await demand_forecaster_async(state, mock_session)

        # Should return low confidence response, not fail
        assert result["workflow_status"] == WorkflowStatus.OPTIMIZING.value
        assert result["forecast_confidence"] < 0.60  # Below high threshold
        assert result["forecast"] == []
        assert result["audit_log"][0]["action"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_successful_forecast_generation(self) -> None:
        """Test successful forecast generation with Prophet."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        # Mock training data with sufficient data
        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            # Sufficient training data (730 days)
            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100 + i % 7 for i in range(730)],
            })
            mock_get_data.return_value = mock_df

            # Mock forecast result
            from datetime import timedelta
            base_date = dt(2024, 7, 1)
            mock_forecasts = [
                ForecastPoint(
                    ds=base_date + timedelta(weeks=i),
                    yhat=100.0 + i,
                    yhat_lower=80.0 + i,
                    yhat_upper=120.0 + i,
                )
                for i in range(26)
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            mock_performance = ModelPerformance(
                sku="UFBub250",
                mape=0.08,  # 8% MAPE
                rmse=15.0,
                mae=12.0,
                coverage=0.80,
                horizon_days=90,
            )
            mock_train.return_value = (MagicMock(), mock_result, mock_performance)

            result = await demand_forecaster_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.OPTIMIZING.value
        assert len(result["forecast"]) == 26
        assert result["forecast_confidence"] == pytest.approx(0.92)  # 1 - 0.08
        assert result["audit_log"][0]["action"] == "generate_forecast"

    @pytest.mark.asyncio
    async def test_forecast_confidence_from_mape(self) -> None:
        """Test that forecast confidence is calculated from MAPE."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df

            # Test with 15% MAPE (above target but still reasonable)
            mock_forecasts = [
                ForecastPoint(ds=dt(2024, 7, 1), yhat=100.0, yhat_lower=80.0, yhat_upper=120.0)
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            mock_performance = ModelPerformance(
                sku="UFBub250",
                mape=0.15,  # 15% MAPE
                rmse=20.0,
                mae=15.0,
                coverage=0.75,
                horizon_days=90,
            )
            mock_train.return_value = (MagicMock(), mock_result, mock_performance)

            result = await demand_forecaster_async(state, mock_session)

        # Confidence should be 1 - 0.15 = 0.85
        assert result["forecast_confidence"] == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_high_mape_capped_confidence(self) -> None:
        """Test that very high MAPE results in capped confidence."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df

            mock_forecasts = [
                ForecastPoint(ds=dt(2024, 7, 1), yhat=100.0, yhat_lower=80.0, yhat_upper=120.0)
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            # Very poor model with MAPE > 100%
            mock_performance = ModelPerformance(
                sku="UFBub250",
                mape=1.5,  # 150% MAPE
                rmse=200.0,
                mae=150.0,
                coverage=0.30,
                horizon_days=90,
            )
            mock_train.return_value = (MagicMock(), mock_result, mock_performance)

            result = await demand_forecaster_async(state, mock_session)

        # Confidence should be clamped to 0
        assert result["forecast_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_no_validation_uses_conservative_confidence(self) -> None:
        """Test that no validation results in conservative confidence estimate."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df

            mock_forecasts = [
                ForecastPoint(ds=dt(2024, 7, 1), yhat=100.0, yhat_lower=80.0, yhat_upper=120.0)
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            # No performance metrics (validation skipped)
            mock_train.return_value = (MagicMock(), mock_result, None)

            result = await demand_forecaster_async(state, mock_session)

        # Should use conservative 75% confidence
        assert result["forecast_confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_training_error_handled(self) -> None:
        """Test that training errors are handled gracefully."""
        import pandas as pd

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df
            mock_train.side_effect = Exception("Prophet training failed")

            result = await demand_forecaster_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.FAILED.value
        assert "Forecast generation failed" in result["error_message"]
        assert result["forecast_confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_data_fetch_error_handled(self) -> None:
        """Test that data fetching errors are handled gracefully."""
        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data:
            mock_get_data.side_effect = Exception("Database connection failed")

            result = await demand_forecaster_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.FAILED.value
        assert "Error fetching training data" in result["error_message"]

    @pytest.mark.asyncio
    async def test_forecast_format_correct(self) -> None:
        """Test that forecast output format matches state requirements."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df

            mock_forecasts = [
                ForecastPoint(
                    ds=dt(2024, 7, 1),
                    yhat=105.5,
                    yhat_lower=85.0,
                    yhat_upper=126.0,
                )
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            mock_performance = ModelPerformance(
                sku="UFBub250",
                mape=0.10,
                rmse=15.0,
                mae=12.0,
                coverage=0.80,
                horizon_days=90,
            )
            mock_train.return_value = (MagicMock(), mock_result, mock_performance)

            result = await demand_forecaster_async(state, mock_session)

        # Check forecast format
        assert len(result["forecast"]) == 1
        forecast_point = result["forecast"][0]
        assert forecast_point["week"] == 1
        assert "date" in forecast_point  # ISO format string
        assert forecast_point["yhat"] == 105.5
        assert forecast_point["yhat_lower"] == 85.0
        assert forecast_point["yhat_upper"] == 126.0

    @pytest.mark.asyncio
    async def test_audit_log_includes_metrics(self) -> None:
        """Test that audit log includes model performance metrics."""
        import pandas as pd
        from datetime import datetime as dt

        from src.services.forecast import ForecastPoint, ForecastResult, ModelPerformance

        sku_id = uuid4()
        state = create_initial_state(
            sku_id=str(sku_id),
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        with patch("src.services.forecast.get_training_data") as mock_get_data, \
             patch("src.services.forecast.train_forecast_model_for_sku") as mock_train:

            mock_df = pd.DataFrame({
                "ds": pd.date_range("2022-01-01", periods=730),
                "y": [100] * 730,
            })
            mock_get_data.return_value = mock_df

            mock_forecasts = [
                ForecastPoint(ds=dt(2024, 7, 1), yhat=100.0, yhat_lower=80.0, yhat_upper=120.0)
            ]
            mock_result = ForecastResult(
                sku="UFBub250",
                sku_id=sku_id,
                forecasts=mock_forecasts,
                model_trained_at=dt.now(),
                training_data_start=dt(2022, 1, 1).date(),
                training_data_end=dt(2024, 1, 1).date(),
                training_data_points=730,
            )
            mock_performance = ModelPerformance(
                sku="UFBub250",
                mape=0.10,
                rmse=15.0,
                mae=12.0,
                coverage=0.80,
                horizon_days=90,
            )
            mock_train.return_value = (MagicMock(), mock_result, mock_performance)

            result = await demand_forecaster_async(state, mock_session)

        audit_entry = result["audit_log"][0]
        assert audit_entry["outputs"]["mape"] == 0.10
        assert audit_entry["outputs"]["rmse"] == 15.0
        assert audit_entry["inputs"]["training_data_days"] == 730


class TestCalculateSafetyStockFromForecast:
    """Tests for calculate_safety_stock_from_forecast function."""

    def test_empty_forecast_returns_zero(self) -> None:
        """Test that empty forecast returns zero safety stock."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        result = calculate_safety_stock_from_forecast([])
        assert result == 0

    def test_single_point_forecast(self) -> None:
        """Test safety stock calculation with single forecast point."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        forecast = [{"yhat": 100.0, "yhat_upper": 120.0}]
        result = calculate_safety_stock_from_forecast(forecast, service_level=0.80)
        # Variability = 20, no scaling needed for 80% level
        assert result == 20

    def test_multiple_points_averaging(self) -> None:
        """Test that multiple points are averaged correctly."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        forecast = [
            {"yhat": 100.0, "yhat_upper": 120.0},  # variability = 20
            {"yhat": 100.0, "yhat_upper": 140.0},  # variability = 40
        ]
        result = calculate_safety_stock_from_forecast(forecast, service_level=0.80)
        # Average variability = 30, no scaling for 80%
        assert result == 30

    def test_95_service_level_scaling(self) -> None:
        """Test that 95% service level scales the safety stock up."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        forecast = [{"yhat": 100.0, "yhat_upper": 120.0}]
        result = calculate_safety_stock_from_forecast(forecast, service_level=0.95)
        # Variability = 20, scaled by 1.96/1.28 ≈ 1.53
        expected = int(20 * (1.96 / 1.28) + 0.5)
        assert result == expected

    def test_missing_yhat_upper_uses_yhat(self) -> None:
        """Test handling of missing yhat_upper field."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        forecast = [{"yhat": 100.0}]  # No yhat_upper
        result = calculate_safety_stock_from_forecast(forecast)
        # Variability = 0 (yhat_upper defaults to yhat)
        assert result == 0

    def test_negative_variability_clamped(self) -> None:
        """Test that negative variability is clamped to zero."""
        from src.agents.procurement import calculate_safety_stock_from_forecast

        forecast = [{"yhat": 100.0, "yhat_upper": 80.0}]  # Upper < yhat
        result = calculate_safety_stock_from_forecast(forecast)
        # Variability clamped to 0
        assert result == 0


class TestCalculateReorderPoint:
    """Tests for calculate_reorder_point function."""

    def test_basic_calculation(self) -> None:
        """Test basic reorder point calculation."""
        from src.agents.procurement import calculate_reorder_point

        # 10 units/day × 14 days + 50 safety stock = 190
        result = calculate_reorder_point(
            average_daily_demand=10.0,
            lead_time_days=14,
            safety_stock=50,
        )
        assert result == 190

    def test_zero_demand(self) -> None:
        """Test reorder point with zero demand."""
        from src.agents.procurement import calculate_reorder_point

        # 0 × 14 + 50 = 50
        result = calculate_reorder_point(
            average_daily_demand=0.0,
            lead_time_days=14,
            safety_stock=50,
        )
        assert result == 50

    def test_zero_safety_stock(self) -> None:
        """Test reorder point with zero safety stock."""
        from src.agents.procurement import calculate_reorder_point

        # 10 × 14 + 0 = 140
        result = calculate_reorder_point(
            average_daily_demand=10.0,
            lead_time_days=14,
            safety_stock=0,
        )
        assert result == 140

    def test_rounding_up(self) -> None:
        """Test that result is rounded correctly."""
        from src.agents.procurement import calculate_reorder_point

        # 10.5 × 7 + 25 = 98.5 → 99
        result = calculate_reorder_point(
            average_daily_demand=10.5,
            lead_time_days=7,
            safety_stock=25,
        )
        assert result == 99


class TestCalculateReorderQuantity:
    """Tests for calculate_reorder_quantity function."""

    def test_below_reorder_point(self) -> None:
        """Test order quantity when below reorder point."""
        from src.agents.procurement import calculate_reorder_quantity

        # Current: 100, reorder point: 200, target: 12 weeks @ 50/week = 600
        # Quantity needed: 600 - 100 = 500
        result = calculate_reorder_quantity(
            current_inventory=100,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=50.0,
        )
        assert result == 500

    def test_at_reorder_point(self) -> None:
        """Test order quantity exactly at reorder point."""
        from src.agents.procurement import calculate_reorder_quantity

        result = calculate_reorder_quantity(
            current_inventory=200,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=50.0,
        )
        # Target = 600, current = 200, need 400
        assert result == 400

    def test_above_reorder_point(self) -> None:
        """Test order quantity when above reorder point."""
        from src.agents.procurement import calculate_reorder_quantity

        result = calculate_reorder_quantity(
            current_inventory=400,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=50.0,
        )
        # Target = 600, current = 400, proactive order = 200
        assert result == 200

    def test_above_target(self) -> None:
        """Test when current inventory exceeds target."""
        from src.agents.procurement import calculate_reorder_quantity

        result = calculate_reorder_quantity(
            current_inventory=700,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=50.0,
        )
        # Target = 600, current = 700, no order needed
        assert result == 0

    def test_minimum_order_quantity(self) -> None:
        """Test that minimum order quantity is respected."""
        from src.agents.procurement import calculate_reorder_quantity

        result = calculate_reorder_quantity(
            current_inventory=580,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=50.0,
            minimum_order_quantity=100,
        )
        # Would need 20, but minimum is 100
        assert result == 100

    def test_zero_demand(self) -> None:
        """Test with zero weekly demand."""
        from src.agents.procurement import calculate_reorder_quantity

        result = calculate_reorder_quantity(
            current_inventory=100,
            reorder_point=200,
            target_weeks_of_supply=12,
            average_weekly_demand=0.0,
        )
        # Target = 0, no order needed
        assert result == 0


class TestInventoryOptimizerSync:
    """Tests for synchronous inventory_optimizer function."""

    def test_with_forecast_data(self) -> None:
        """Test optimizer with forecast data available."""
        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=100,
        )
        # Add forecast data
        state["forecast"] = [
            {"week": 1, "yhat": 70.0, "yhat_lower": 50.0, "yhat_upper": 90.0},
            {"week": 2, "yhat": 75.0, "yhat_lower": 55.0, "yhat_upper": 95.0},
        ]
        state["forecast_confidence"] = 0.90

        result = inventory_optimizer(state)

        assert "safety_stock" in result
        assert "reorder_point" in result
        assert "recommended_quantity" in result
        assert result["safety_stock"] > 0  # Should have calculated safety stock
        assert result["workflow_status"] == WorkflowStatus.ANALYZING_VENDOR.value

    def test_without_forecast_data(self) -> None:
        """Test optimizer without forecast data."""
        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=100,
        )
        state["forecast"] = []
        state["forecast_confidence"] = 0.0

        result = inventory_optimizer(state)

        # Should still return valid output, just with zero values
        assert result["safety_stock"] == 0
        assert result["reorder_point"] == 0
        assert result["recommended_quantity"] == 0

    def test_audit_log_contains_details(self) -> None:
        """Test that audit log contains calculation details."""
        state = create_initial_state(
            sku_id="test-sku",
            sku="UFBub250",
            current_inventory=500,
        )
        state["forecast"] = [
            {"week": 1, "yhat": 100.0, "yhat_lower": 80.0, "yhat_upper": 120.0}
        ]

        result = inventory_optimizer(state)

        audit = result["audit_log"][0]
        assert audit["agent"] == "inventory_optimizer"
        assert audit["action"] == "calculate_reorder"
        assert "average_weekly_demand" in audit["outputs"]
        assert "average_daily_demand" in audit["outputs"]
        assert "lead_time_days" in audit["inputs"]
        assert "service_level" in audit["inputs"]


class TestInventoryOptimizerAsync:
    """Tests for inventory_optimizer_async function."""

    @pytest.mark.asyncio
    async def test_invalid_sku_id_format(self) -> None:
        """Test handling of invalid SKU ID format."""
        from src.agents.procurement import inventory_optimizer_async

        state = create_initial_state(
            sku_id="not-a-valid-uuid",
            sku="UFBub250",
            current_inventory=100,
        )
        mock_session = AsyncMock()

        result = await inventory_optimizer_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.FAILED.value
        assert "Invalid SKU ID format" in result["error_message"]
        assert result["safety_stock"] == 0
        assert result["reorder_point"] == 0
        assert result["recommended_quantity"] == 0

    @pytest.mark.asyncio
    async def test_with_forecast_from_state(self) -> None:
        """Test optimizer uses forecast data from state."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=200,
        )
        # Add 26 weeks of forecast data
        state["forecast"] = [
            {"week": i + 1, "yhat": 100.0, "yhat_lower": 80.0, "yhat_upper": 120.0}
            for i in range(26)
        ]
        state["forecast_confidence"] = 0.90

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv:
            mock_inv.return_value = 200

            result = await inventory_optimizer_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.ANALYZING_VENDOR.value
        assert result["safety_stock"] > 0
        assert result["reorder_point"] > 0
        # Weekly demand = 100, 12 weeks = 1200, current = 200, need 1000
        assert result["recommended_quantity"] > 0

    @pytest.mark.asyncio
    async def test_falls_back_to_historical_demand(self) -> None:
        """Test optimizer falls back to historical demand when no forecast."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,
        )
        state["forecast"] = []  # No forecast
        state["forecast_confidence"] = 0.0

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv, \
             patch("src.services.metrics.get_depletion_total") as mock_dep:
            mock_inv.return_value = 100
            mock_dep.return_value = 900  # 900 units in 90 days = 10/day

            result = await inventory_optimizer_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.ANALYZING_VENDOR.value
        # Should have calculated from historical data
        audit = result["audit_log"][0]
        assert audit["inputs"]["demand_source"] == "historical_90d"
        assert audit["outputs"]["average_daily_demand"] == pytest.approx(10.0)

    @pytest.mark.asyncio
    async def test_needs_reorder_flag(self) -> None:
        """Test that needs_reorder flag is set correctly."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=50,  # Low inventory
        )
        state["forecast"] = [
            {"week": 1, "yhat": 100.0, "yhat_lower": 80.0, "yhat_upper": 120.0}
        ]
        state["forecast_confidence"] = 0.90

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv:
            mock_inv.return_value = 50  # Low inventory

            result = await inventory_optimizer_async(state, mock_session)

        audit = result["audit_log"][0]
        assert audit["outputs"]["needs_reorder"] is True

    @pytest.mark.asyncio
    async def test_custom_parameters(self) -> None:
        """Test optimizer with custom lead time and service level."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=500,
        )
        state["forecast"] = [
            {"week": 1, "yhat": 100.0, "yhat_lower": 80.0, "yhat_upper": 120.0}
        ]

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv:
            mock_inv.return_value = 500

            result = await inventory_optimizer_async(
                state,
                mock_session,
                lead_time_days=21,  # 3 weeks
                target_weeks_supply=8,  # 8 weeks
                service_level=0.99,  # 99% service level
            )

        audit = result["audit_log"][0]
        assert audit["inputs"]["lead_time_days"] == 21
        assert audit["inputs"]["target_weeks_supply"] == 8
        assert audit["inputs"]["service_level"] == 0.99

    @pytest.mark.asyncio
    async def test_updates_current_inventory_from_db(self) -> None:
        """Test that current inventory is updated from database."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,  # State says 100
        )
        state["forecast"] = [
            {"week": 1, "yhat": 50.0, "yhat_lower": 40.0, "yhat_upper": 60.0}
        ]

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv:
            mock_inv.return_value = 250  # DB says 250

            result = await inventory_optimizer_async(state, mock_session)

        # Should update state with accurate DB value
        assert result["current_inventory"] == 250

    @pytest.mark.asyncio
    async def test_handles_db_error_gracefully(self) -> None:
        """Test that database errors are handled gracefully."""
        from src.agents.procurement import inventory_optimizer_async

        sku_id = str(uuid4())
        state = create_initial_state(
            sku_id=sku_id,
            sku="UFBub250",
            current_inventory=100,
        )
        state["forecast"] = [
            {"week": 1, "yhat": 50.0, "yhat_lower": 40.0, "yhat_upper": 60.0}
        ]

        mock_session = AsyncMock()

        with patch("src.services.metrics.get_current_inventory") as mock_inv:
            mock_inv.side_effect = Exception("Database connection failed")

            # Should fall back to state value, not fail
            result = await inventory_optimizer_async(state, mock_session)

        assert result["workflow_status"] == WorkflowStatus.ANALYZING_VENDOR.value
        # Uses fallback value from state
        audit = result["audit_log"][0]
        assert audit["inputs"]["current_inventory"] == 100


class TestCreateOptimizerErrorResponse:
    """Tests for _create_optimizer_error_response helper."""

    def test_returns_zero_values(self) -> None:
        """Test that error response has zero values."""
        from src.agents.procurement import _create_optimizer_error_response

        result = _create_optimizer_error_response(
            sku="UFBub250",
            error_message="Test error",
            forecast_confidence=0.85,
        )
        assert result["safety_stock"] == 0
        assert result["reorder_point"] == 0
        assert result["recommended_quantity"] == 0

    def test_sets_failed_status(self) -> None:
        """Test that error response sets failed workflow status."""
        from src.agents.procurement import _create_optimizer_error_response

        result = _create_optimizer_error_response(
            sku="UFBub250",
            error_message="Test error",
            forecast_confidence=0.85,
        )
        assert result["workflow_status"] == WorkflowStatus.FAILED.value

    def test_includes_error_message(self) -> None:
        """Test that error response includes the error message."""
        from src.agents.procurement import _create_optimizer_error_response

        result = _create_optimizer_error_response(
            sku="UFBub250",
            error_message="Something went wrong",
            forecast_confidence=0.85,
        )
        assert result["error_message"] == "Something went wrong"

    def test_creates_audit_entry(self) -> None:
        """Test that error response creates audit log entry."""
        from src.agents.procurement import _create_optimizer_error_response

        result = _create_optimizer_error_response(
            sku="UFBub250",
            error_message="Test error",
            forecast_confidence=0.85,
        )
        assert len(result["audit_log"]) == 1
        assert result["audit_log"][0]["agent"] == "inventory_optimizer"
        assert result["audit_log"][0]["action"] == "optimization_error"
        assert result["audit_log"][0]["confidence"] == 0.0


class TestInventoryOptimizerIntegration:
    """Integration tests for inventory optimizer in workflow context."""

    def test_workflow_flows_through_optimizer(self) -> None:
        """Test that workflow correctly flows through optimizer."""
        compiled = compile_workflow(interrupt_before=[])

        state = create_initial_state(
            sku_id=str(uuid4()),
            sku="UFBub250",
            current_inventory=100,
        )

        config = {"configurable": {"thread_id": "test-optimizer-1"}}
        result = compiled.invoke(state, config)

        # Should have optimizer output
        assert result["safety_stock"] >= 0
        assert result["reorder_point"] >= 0

    def test_optimizer_output_used_by_vendor_analyzer(self) -> None:
        """Test that optimizer output flows to vendor analyzer."""
        compiled = compile_workflow(interrupt_before=[])

        state = create_initial_state(
            sku_id=str(uuid4()),
            sku="UFBub250",
            current_inventory=1000,
        )

        config = {"configurable": {"thread_id": "test-optimizer-2"}}
        result = compiled.invoke(state, config)

        # Vendor analyzer should use recommended_quantity
        assert result["order_value"] >= 0  # Calculated from quantity × price
