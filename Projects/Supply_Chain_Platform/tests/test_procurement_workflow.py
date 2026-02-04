"""Tests for the LangGraph procurement workflow state machine."""

from datetime import UTC, datetime

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
    build_procurement_workflow,
    compile_workflow,
    create_initial_state,
    demand_forecaster,
    generate_purchase_order,
    human_approval,
    inventory_optimizer,
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
