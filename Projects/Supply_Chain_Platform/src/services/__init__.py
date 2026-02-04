"""Business logic services for the supply chain platform."""

from src.services.distributor import (
    ParsedRow,
    ParseResult,
    RowError,
    parse_rndc_report,
)
from src.services.metrics import (
    DOHMetrics,
    calculate_daily_depletion_rate,
    calculate_doh_t30,
    calculate_doh_t30_all_skus,
    calculate_doh_t30_for_sku,
    get_current_inventory,
    get_depletion_total,
)
from src.services.winedirect import (
    WineDirectAPIError,
    WineDirectAuthError,
    WineDirectClient,
)

__all__ = [
    "DOHMetrics",
    "ParsedRow",
    "ParseResult",
    "RowError",
    "WineDirectAPIError",
    "WineDirectAuthError",
    "WineDirectClient",
    "calculate_doh_t30",
    "calculate_daily_depletion_rate",
    "calculate_doh_t30_all_skus",
    "calculate_doh_t30_for_sku",
    "get_current_inventory",
    "get_depletion_total",
    "parse_rndc_report",
]
