/**
 * Comprehensive demo data for the Une Femme Supply Chain dashboard.
 *
 * All data is deterministic (no Math.random) so SSR/CSR stays consistent.
 * Values are based on real business profiles from the seed data script.
 */
import type {
  MetricsResponse,
  SKUMetrics,
  DOHMetrics,
  ShipDepRatio,
  VelocityTrend,
  InventoryResponse,
  InventoryItem,
  DepletionResponse,
  DepletionEvent,
  AuditLogListResponse,
  AuditLog,
  ReviewQueueResponse,
  ReviewQueueStats,
  EmailClassification,
  EmailCategory,
} from "./api-types"

// ── Helpers ──────────────────────────────────────────────────────────

/** Deterministic noise in [0,1) for any integer seed */
function noise(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
  return x - Math.floor(x)
}

function daysAgo(n: number): Date {
  const d = new Date()
  d.setHours(12, 0, 0, 0)
  d.setDate(d.getDate() - n)
  return d
}

function hoursAgo(n: number): Date {
  const d = new Date()
  d.setMinutes(0, 0, 0)
  d.setHours(d.getHours() - n)
  return d
}

function toISO(d: Date): string {
  return d.toISOString()
}

function fakeUUID(a: number, b: number): string {
  const p1 = ((a * 2654435761) >>> 0).toString(16).padStart(8, "0")
  const p2 = ((b * 2246822519) >>> 0).toString(16).padStart(8, "0")
  return `${p1.slice(0, 8)}-${p1.slice(0, 4)}-4${p1.slice(5, 8)}-a${p2.slice(1, 4)}-${p2}000000`.slice(0, 36)
}

// ── Constants ────────────────────────────────────────────────────────

const WAREHOUSES = ["Napa Valley Warehouse", "LA Distribution Center", "New York Warehouse"]
const WH_CODES = ["WH01", "WH02", "WH03"]

const CUSTOMERS = [
  "Napa Valley Wine Shop",
  "San Francisco Spirits",
  "LA Wine Collective",
  "NYC Fine Wines",
  "Chicago Wine Market",
  "Boston Wine Exchange",
  "Denver Wine Room",
  "Seattle Wine Merchants",
  "Austin Wine Society",
  "Portland Wine Bar",
  "The Wine Cellar",
  "Vineyard Selections",
  "Coastal Wine Co.",
  "Urban Vine",
  "Terroir Imports",
  "Golden Gate Bottles",
  "SoHo Wine & Spirits",
  "Beverly Hills Vino",
  "Capitol Wine Group",
  "Pacific Wine Traders",
]

const SKU_IDS: Record<string, string> = {
  UFBub250: "sku-bub-250-0001-000000000001",
  UFRos250: "sku-ros-250-0002-000000000002",
  UFRed250: "sku-red-250-0003-000000000003",
  UFCha250: "sku-cha-250-0004-000000000004",
}

// ── Metrics Data ─────────────────────────────────────────────────────

const now = toISO(new Date())

function buildDOH(
  sku: string,
  currentInv: number,
  dohT30: number,
  deplet30: number,
  dailyR30: number,
  dohT90: number,
  deplet90: number,
  dailyR90: number,
): DOHMetrics {
  return {
    sku,
    sku_id: SKU_IDS[sku],
    current_inventory: currentInv,
    doh_t30: dohT30,
    depletion_30d: deplet30,
    daily_rate_30d: dailyR30,
    doh_t90: dohT90,
    depletion_90d: deplet90,
    daily_rate_90d: dailyR90,
    calculated_at: now,
  }
}

function buildShipDep(
  sku: string,
  ship30: number,
  dep30: number,
  ship90: number,
  dep90: number,
): ShipDepRatio {
  return {
    sku,
    sku_id: SKU_IDS[sku],
    shipment_30d: ship30,
    depletion_30d: dep30,
    ratio_30d: dep30 > 0 ? +(ship30 / dep30).toFixed(2) : null,
    shipment_90d: ship90,
    depletion_90d: dep90,
    ratio_90d: dep90 > 0 ? +(ship90 / dep90).toFixed(2) : null,
    calculated_at: now,
  }
}

function buildVelocity(
  sku: string,
  dep30: number,
  dep90: number,
  ship30: number,
  ship90: number,
): VelocityTrend {
  const dr30d = +(dep30 / 30).toFixed(1)
  const dr90d = +(dep90 / 90).toFixed(1)
  const sr30d = +(ship30 / 30).toFixed(1)
  const sr90d = +(ship90 / 90).toFixed(1)
  return {
    sku,
    sku_id: SKU_IDS[sku],
    depletion_30d: dep30,
    depletion_90d: dep90,
    daily_rate_30d_dep: dr30d,
    daily_rate_90d_dep: dr90d,
    velocity_trend_dep: dr90d > 0 ? +(dr30d / dr90d).toFixed(2) : null,
    shipment_30d: ship30,
    shipment_90d: ship90,
    daily_rate_30d_ship: sr30d,
    daily_rate_90d_ship: sr90d,
    velocity_trend_ship: sr90d > 0 ? +(sr30d / sr90d).toFixed(2) : null,
    calculated_at: now,
  }
}

const METRICS: SKUMetrics[] = [
  // UFBub250 — Healthy (~47 DOH)
  {
    sku: "UFBub250",
    sku_id: SKU_IDS.UFBub250,
    doh: buildDOH("UFBub250", 2350, 47, 1500, 50, 42, 5040, 56),
    ship_dep_ratio: buildShipDep("UFBub250", 1600, 1500, 5200, 5040),
    velocity_trend: buildVelocity("UFBub250", 1500, 5040, 1600, 5200),
    calculated_at: now,
  },
  // UFRos250 — Warning (~20 DOH, accelerating demand)
  {
    sku: "UFRos250",
    sku_id: SKU_IDS.UFRos250,
    doh: buildDOH("UFRos250", 1100, 20, 1650, 55, 28, 3600, 40),
    ship_dep_ratio: buildShipDep("UFRos250", 1200, 1650, 3400, 3600),
    velocity_trend: buildVelocity("UFRos250", 1650, 3600, 1200, 3400),
    calculated_at: now,
  },
  // UFRed250 — Overstocked (~90 DOH)
  {
    sku: "UFRed250",
    sku_id: SKU_IDS.UFRed250,
    doh: buildDOH("UFRed250", 1800, 90, 600, 20, 85, 1890, 21),
    ship_dep_ratio: buildShipDep("UFRed250", 800, 600, 2100, 1890),
    velocity_trend: buildVelocity("UFRed250", 600, 1890, 800, 2100),
    calculated_at: now,
  },
  // UFCha250 — Critical (~8 DOH)
  {
    sku: "UFCha250",
    sku_id: SKU_IDS.UFCha250,
    doh: buildDOH("UFCha250", 520, 8, 1950, 65, 12, 4860, 54),
    ship_dep_ratio: buildShipDep("UFCha250", 900, 1950, 3200, 4860),
    velocity_trend: buildVelocity("UFCha250", 1950, 4860, 900, 3200),
    calculated_at: now,
  },
]

// ── Public Demo Data Generators ──────────────────────────────────────

export function getDemoMetrics(): MetricsResponse {
  return {
    skus: METRICS,
    total_skus: 4,
    warehouse_id: null,
    distributor_id: null,
    calculated_at: now,
  }
}

export function getDemoSkuMetrics(sku: string): SKUMetrics {
  return METRICS.find((m) => m.sku === sku) ?? METRICS[0]
}

export function getDemoInventory(): InventoryResponse {
  const items: InventoryItem[] = [
    // UFBub250 — 2350 total
    { sku: "UFBub250", quantity: 900, pool: "Sellable", warehouse: "Napa Valley Warehouse" },
    { sku: "UFBub250", quantity: 850, pool: "Sellable", warehouse: "LA Distribution Center" },
    { sku: "UFBub250", quantity: 600, pool: "Sellable", warehouse: "New York Warehouse" },
    // UFRos250 — 1100 total
    { sku: "UFRos250", quantity: 450, pool: "Sellable", warehouse: "Napa Valley Warehouse" },
    { sku: "UFRos250", quantity: 400, pool: "Sellable", warehouse: "LA Distribution Center" },
    { sku: "UFRos250", quantity: 250, pool: "Sellable", warehouse: "New York Warehouse" },
    // UFRed250 — 1800 total
    { sku: "UFRed250", quantity: 700, pool: "Sellable", warehouse: "Napa Valley Warehouse" },
    { sku: "UFRed250", quantity: 650, pool: "Sellable", warehouse: "LA Distribution Center" },
    { sku: "UFRed250", quantity: 450, pool: "Sellable", warehouse: "New York Warehouse" },
    // UFCha250 — 520 total
    { sku: "UFCha250", quantity: 220, pool: "Sellable", warehouse: "Napa Valley Warehouse" },
    { sku: "UFCha250", quantity: 180, pool: "Sellable", warehouse: "LA Distribution Center" },
    { sku: "UFCha250", quantity: 120, pool: "Sellable", warehouse: "New York Warehouse" },
  ]
  return { items, total_items: items.length }
}

export function getDemoInventoryBySku(sku: string): InventoryItem[] {
  return getDemoInventory().items.filter((i) => i.sku === sku)
}

// Daily depletion rates per SKU
const DEPLETION_PROFILES: Record<string, { base: number; variance: number; trend: number }> = {
  UFBub250: { base: 50, variance: 8, trend: 0 },
  UFRos250: { base: 40, variance: 10, trend: 0.5 }, // accelerating
  UFRed250: { base: 20, variance: 5, trend: 0 },
  UFCha250: { base: 65, variance: 12, trend: 0 },
}

export function getDemoDepletionEvents(params: {
  sku?: string
  start_date?: string
  end_date?: string
}): DepletionResponse {
  const skus = params.sku ? [params.sku] : ["UFBub250", "UFRos250", "UFRed250", "UFCha250"]
  const rangeDays = params.start_date
    ? Math.ceil((Date.now() - new Date(params.start_date).getTime()) / 86400000)
    : 30
  const events: DepletionEvent[] = []
  let eventIdx = 0

  for (const sku of skus) {
    const profile = DEPLETION_PROFILES[sku] ?? { base: 30, variance: 5, trend: 0 }
    for (let d = 0; d < rangeDays; d++) {
      // 1-3 events per day per SKU
      const eventsPerDay = 1 + Math.floor(noise(d * 100 + eventIdx) * 3)
      const dayRate = profile.base + profile.trend * (rangeDays - d) / 3
      const dayTotal = Math.round(dayRate + (noise(d * 7 + eventIdx + 1) - 0.5) * profile.variance * 2)

      for (let e = 0; e < eventsPerDay; e++) {
        const qty = Math.max(1, Math.round(dayTotal / eventsPerDay + (noise(d * 13 + e * 7 + eventIdx) - 0.5) * 10))
        const custIdx = Math.floor(noise(d * 17 + e * 23 + eventIdx) * CUSTOMERS.length)
        const whIdx = Math.floor(noise(d * 31 + e * 11 + eventIdx) * 3)
        const hour = 8 + Math.floor(noise(d * 41 + e * 3 + eventIdx) * 10)
        const date = daysAgo(d)
        date.setHours(hour, Math.floor(noise(d * 53 + e) * 60))

        events.push({
          sku,
          quantity: qty,
          event_time: toISO(date),
          order_id: `WD-${String(2026000 + eventIdx).padStart(7, "0")}`,
          customer: CUSTOMERS[custIdx],
          warehouse: WAREHOUSES[whIdx],
        })
        eventIdx++
      }
    }
  }

  // Sort newest first
  events.sort((a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime())

  return {
    events,
    total_events: events.length,
    start_date: params.start_date ?? toISO(daysAgo(rangeDays)),
    end_date: params.end_date ?? toISO(new Date()),
  }
}

// ── Audit Logs ───────────────────────────────────────────────────────

const AUDIT_ENTRIES: Omit<AuditLog, "id" | "created_at">[] = [
  // Recent demand forecasting
  { workflow_id: "wf-forecast-001", thread_id: null, timestamp: toISO(hoursAgo(1)), agent: "demand_forecaster", action: "generate_forecast", reasoning: "Generated 26-week forecast for UFCha250. MAPE 14.1% — above target. Demand acceleration detected (+20% 30d vs 90d). Recommending safety stock increase.", inputs: { sku: "UFCha250", training_points: 312 }, outputs: { mape: 0.141, weeks: 26 }, confidence: 0.78, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-forecast-001", thread_id: null, timestamp: toISO(hoursAgo(1.5)), agent: "demand_forecaster", action: "generate_forecast", reasoning: "Generated 26-week forecast for UFBub250. MAPE 8.2% — within target. Stable demand pattern, slight seasonal uplift expected for spring.", inputs: { sku: "UFBub250", training_points: 312 }, outputs: { mape: 0.082, weeks: 26 }, confidence: 0.92, sku_id: SKU_IDS.UFBub250, sku: "UFBub250" },
  { workflow_id: "wf-forecast-001", thread_id: null, timestamp: toISO(hoursAgo(2)), agent: "demand_forecaster", action: "generate_forecast", reasoning: "Generated 26-week forecast for UFRos250. MAPE 12.5% — near target boundary. Strong acceleration trend: 30d rate 38% above 90d average. Valentine's Day effect tapering.", inputs: { sku: "UFRos250", training_points: 312 }, outputs: { mape: 0.125, weeks: 26 }, confidence: 0.82, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },
  { workflow_id: "wf-forecast-001", thread_id: null, timestamp: toISO(hoursAgo(2.5)), agent: "demand_forecaster", action: "generate_forecast", reasoning: "Generated 26-week forecast for UFRed250. MAPE 6.8% — excellent fit. Stable declining trend consistent with seasonal patterns. No intervention needed.", inputs: { sku: "UFRed250", training_points: 312 }, outputs: { mape: 0.068, weeks: 26 }, confidence: 0.95, sku_id: SKU_IDS.UFRed250, sku: "UFRed250" },

  // Inventory monitoring
  { workflow_id: "wf-monitor-002", thread_id: null, timestamp: toISO(hoursAgo(3)), agent: "inventory_monitor", action: "check_levels", reasoning: "CRITICAL: UFCha250 at 520 units with DOH T30 of 8 days. Below 14-day critical threshold. Immediate reorder required. Daily burn rate 65 units.", inputs: { sku: "UFCha250" }, outputs: { doh_t30: 8, status: "critical" }, confidence: 0.97, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-monitor-002", thread_id: null, timestamp: toISO(hoursAgo(3.2)), agent: "inventory_monitor", action: "check_levels", reasoning: "WARNING: UFRos250 at 1,100 units with DOH T30 of 20 days. Demand accelerating — 30d depletion rate 38% above 90d average. Monitor closely.", inputs: { sku: "UFRos250" }, outputs: { doh_t30: 20, status: "warning" }, confidence: 0.94, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },
  { workflow_id: "wf-monitor-002", thread_id: null, timestamp: toISO(hoursAgo(3.4)), agent: "inventory_monitor", action: "check_levels", reasoning: "HEALTHY: UFBub250 at 2,350 units with DOH T30 of 47 days. Shipment:Depletion ratio balanced at 1.07. No action required.", inputs: { sku: "UFBub250" }, outputs: { doh_t30: 47, status: "healthy" }, confidence: 0.98, sku_id: SKU_IDS.UFBub250, sku: "UFBub250" },
  { workflow_id: "wf-monitor-002", thread_id: null, timestamp: toISO(hoursAgo(3.6)), agent: "inventory_monitor", action: "check_levels", reasoning: "OVERSTOCKED: UFRed250 at 1,800 units with DOH T30 of 90 days. Consider reducing next shipment or running promotion. Holding cost increasing.", inputs: { sku: "UFRed250" }, outputs: { doh_t30: 90, status: "overstocked" }, confidence: 0.96, sku_id: SKU_IDS.UFRed250, sku: "UFRed250" },

  // Procurement planning
  { workflow_id: "wf-procure-003", thread_id: "thr-003-a", timestamp: toISO(hoursAgo(4)), agent: "procurement_planner", action: "evaluate_reorder", reasoning: "UFCha250 below reorder point (650 units). Current: 520 units. Recommended order: 3,000 units (6-week coverage at 65/day rate + 15% safety buffer). Estimated value $12,600.", inputs: { sku: "UFCha250", current: 520, reorder_point: 650 }, outputs: { recommended_qty: 3000, estimated_value: 12600 }, confidence: 0.91, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-procure-003", thread_id: "thr-003-b", timestamp: toISO(hoursAgo(4.5)), agent: "procurement_planner", action: "evaluate_reorder", reasoning: "UFRos250 approaching reorder point (1,200 units). Current: 1,100 units. Recommend preemptive order due to acceleration trend. 2,500 units ($8,750) for 5-week coverage.", inputs: { sku: "UFRos250", current: 1100, reorder_point: 1200 }, outputs: { recommended_qty: 2500, estimated_value: 8750 }, confidence: 0.86, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },

  // Vendor selection
  { workflow_id: "wf-procure-003", thread_id: "thr-003-a", timestamp: toISO(hoursAgo(5)), agent: "vendor_selector", action: "compare_vendors", reasoning: "Evaluated 3 vendors for UFCha250 order. Napa Bottling Co. selected: best unit price ($4.20), 7-day lead time, 98% on-time delivery rate. Pacific Coast ($4.50, 5-day) and Golden State ($3.90, 14-day) also considered.", inputs: { sku: "UFCha250", vendors: 3 }, outputs: { selected: "Napa Bottling Co.", unit_price: 4.20, lead_time_days: 7 }, confidence: 0.89, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-procure-003", thread_id: "thr-003-b", timestamp: toISO(hoursAgo(5.5)), agent: "vendor_selector", action: "compare_vendors", reasoning: "Evaluated 3 vendors for UFRos250 order. Pacific Coast Supplies selected: fastest lead time (5 days) critical for accelerating demand. Unit price $3.50 competitive.", inputs: { sku: "UFRos250", vendors: 3 }, outputs: { selected: "Pacific Coast Supplies", unit_price: 3.50, lead_time_days: 5 }, confidence: 0.87, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },

  // Approval routing
  { workflow_id: "wf-procure-003", thread_id: "thr-003-a", timestamp: toISO(hoursAgo(6)), agent: "approval_router", action: "route_for_approval", reasoning: "UFCha250 order value $12,600 exceeds $10K threshold. Routed to executive review (Lisa, Finance Director). Urgency: HIGH — 8 days inventory remaining.", inputs: { order_value: 12600, sku: "UFCha250" }, outputs: { approval_level: "executive", assigned_to: "Lisa" }, confidence: 0.95, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-procure-003", thread_id: "thr-003-b", timestamp: toISO(hoursAgo(6.5)), agent: "approval_router", action: "route_for_approval", reasoning: "UFRos250 order value $8,750 in $5K-$10K range. Routed to manager review (Sarah, Supply Chain Manager). Urgency: MEDIUM — 20 days remaining.", inputs: { order_value: 8750, sku: "UFRos250" }, outputs: { approval_level: "manager", assigned_to: "Sarah" }, confidence: 0.93, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },

  // Email classification
  { workflow_id: "wf-email-004", thread_id: null, timestamp: toISO(hoursAgo(7)), agent: "email_classifier", action: "classify_email", reasoning: "Subject contains 'PO #' pattern and attachment is PDF. Classified as Purchase Order with high confidence.", inputs: { subject: "PO #4521 — RNDC California" }, outputs: { category: "PO", confidence: 0.94 }, confidence: 0.94, sku_id: null, sku: null },
  { workflow_id: "wf-email-004", thread_id: null, timestamp: toISO(hoursAgo(7.5)), agent: "email_classifier", action: "classify_email", reasoning: "BOL from freight carrier with tracking number and shipment details. Classified as Bill of Lading.", inputs: { subject: "BOL — Shipment #TRK-89012" }, outputs: { category: "BOL", confidence: 0.91 }, confidence: 0.91, sku_id: null, sku: null },
  { workflow_id: "wf-email-004", thread_id: null, timestamp: toISO(hoursAgo(8)), agent: "email_classifier", action: "classify_email", reasoning: "Invoice from Napa Bottling Co. for recent order. Amount matches open PO. Classified as Invoice.", inputs: { subject: "Invoice INV-2026-0342" }, outputs: { category: "INVOICE", confidence: 0.88 }, confidence: 0.88, sku_id: null, sku: null },

  // Data sync events
  { workflow_id: "wf-sync-005", thread_id: null, timestamp: toISO(hoursAgo(10)), agent: "data_sync", action: "winedirect_sync", reasoning: "Successfully synced WineDirect sellable inventory. 4 SKUs updated across 3 warehouses. Total sellable: 5,770 units. Next sync in 60 minutes.", inputs: { source: "WineDirect ANWD" }, outputs: { skus_updated: 4, warehouses: 3, total_units: 5770 }, confidence: 1.0, sku_id: null, sku: null },
  { workflow_id: "wf-sync-005", thread_id: null, timestamp: toISO(hoursAgo(12)), agent: "data_sync", action: "distributor_ingest", reasoning: "Processed RNDC depletion report. 142 rows parsed, 139 matched to tracked SKUs, 3 unmatched items flagged for review.", inputs: { distributor: "RNDC", filename: "rndc_depletions_feb_2026.csv" }, outputs: { total_rows: 142, matched: 139, unmatched: 3 }, confidence: 0.98, sku_id: null, sku: null },

  // Historical entries (past days)
  { workflow_id: "wf-monitor-006", thread_id: null, timestamp: toISO(daysAgo(1)), agent: "inventory_monitor", action: "daily_summary", reasoning: "Daily summary: UFCha250 dropped to critical (9 DOH). UFRos250 still in warning zone (21 DOH). UFBub250 healthy (48 DOH). UFRed250 overstocked (91 DOH). Two procurement workflows initiated.", inputs: {}, outputs: { critical: 1, warning: 1, healthy: 1, overstocked: 1 }, confidence: 0.99, sku_id: null, sku: null },
  { workflow_id: "wf-forecast-007", thread_id: null, timestamp: toISO(daysAgo(1)), agent: "demand_forecaster", action: "weekly_retrain", reasoning: "Weekly model retraining complete. All 4 SKU models updated with latest 7 days of data. Avg MAPE improved from 11.2% to 10.4%. UFRos250 model flagged for manual review due to trend change.", inputs: { models: 4 }, outputs: { avg_mape: 0.104, improved: true }, confidence: 0.90, sku_id: null, sku: null },
  { workflow_id: "wf-alert-008", thread_id: null, timestamp: toISO(daysAgo(1)), agent: "alert_manager", action: "send_slack_alert", reasoning: "Slack alert sent for UFCha250 critical stock level. Notified #supply-chain channel. Alert includes: current inventory (540), DOH (9), daily burn rate (65), recommended action.", inputs: { channel: "#supply-chain" }, outputs: { sent: true, alert_type: "critical_stock" }, confidence: 1.0, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },

  { workflow_id: "wf-monitor-009", thread_id: null, timestamp: toISO(daysAgo(2)), agent: "inventory_monitor", action: "check_levels", reasoning: "UFCha250 at 610 units, DOH T30: 10 days. Approaching critical threshold. Procurement workflow already in progress.", inputs: { sku: "UFCha250" }, outputs: { doh_t30: 10, status: "warning" }, confidence: 0.96, sku_id: SKU_IDS.UFCha250, sku: "UFCha250" },
  { workflow_id: "wf-sync-010", thread_id: null, timestamp: toISO(daysAgo(2)), agent: "data_sync", action: "winedirect_sync", reasoning: "WineDirect sync completed. Inventory positions updated. Notable: UFBub250 received shipment of 200 units at WH02.", inputs: { source: "WineDirect ANWD" }, outputs: { skus_updated: 4, total_units: 5890 }, confidence: 1.0, sku_id: null, sku: null },

  { workflow_id: "wf-email-011", thread_id: null, timestamp: toISO(daysAgo(2)), agent: "email_classifier", action: "classify_email", reasoning: "General inquiry from distributor about availability. No actionable document attached. Classified as GENERAL.", inputs: { subject: "RE: Spring allocation availability?" }, outputs: { category: "GENERAL", confidence: 0.72 }, confidence: 0.72, sku_id: null, sku: null },
  { workflow_id: "wf-email-011", thread_id: null, timestamp: toISO(daysAgo(2)), agent: "email_classifier", action: "flag_for_review", reasoning: "Low confidence classification (72%). Subject ambiguous — could be PO intent. Flagged for human review.", inputs: { classification_id: "cls-028" }, outputs: { needs_review: true }, confidence: 0.72, sku_id: null, sku: null },

  { workflow_id: "wf-procure-012", thread_id: "thr-012-a", timestamp: toISO(daysAgo(3)), agent: "procurement_planner", action: "evaluate_reorder", reasoning: "UFBub250 routine restock evaluation. Current inventory adequate (2,400 units, 48 DOH). Next reorder point in ~17 days. No immediate action.", inputs: { sku: "UFBub250", current: 2400 }, outputs: { action: "no_reorder", next_eval_days: 7 }, confidence: 0.93, sku_id: SKU_IDS.UFBub250, sku: "UFBub250" },
  { workflow_id: "wf-monitor-013", thread_id: null, timestamp: toISO(daysAgo(3)), agent: "inventory_monitor", action: "compute_doh", reasoning: "Refreshed materialized views for DOH_T30 and DOH_T90. All SKU metrics recalculated. Largest change: UFRos250 DOH dropped from 24 to 22 days.", inputs: {}, outputs: { views_refreshed: 2 }, confidence: 1.0, sku_id: null, sku: null },

  { workflow_id: "wf-sync-014", thread_id: null, timestamp: toISO(daysAgo(4)), agent: "data_sync", action: "distributor_ingest", reasoning: "Processed Southern Glazers weekly report. 87 depletion events across 4 SKUs. UFRos250 depletions 18% above previous week.", inputs: { distributor: "Southern Glazers", filename: "sgz_weekly_020526.xlsx" }, outputs: { total_rows: 87, matched: 85, unmatched: 2 }, confidence: 0.97, sku_id: null, sku: null },
  { workflow_id: "wf-alert-015", thread_id: null, timestamp: toISO(daysAgo(4)), agent: "alert_manager", action: "send_slack_alert", reasoning: "Warning alert for UFRos250: demand acceleration detected. 30-day rate 38% above 90-day average. Notified Sarah (Supply Chain Manager).", inputs: { channel: "#supply-chain" }, outputs: { sent: true, alert_type: "demand_acceleration" }, confidence: 0.95, sku_id: SKU_IDS.UFRos250, sku: "UFRos250" },

  { workflow_id: "wf-email-016", thread_id: null, timestamp: toISO(daysAgo(5)), agent: "email_classifier", action: "classify_email", reasoning: "PO from Winebow for UFBub250 and UFRos250. Two SKUs referenced. Attachment: purchase_order_WB4401.pdf.", inputs: { subject: "PO #WB-4401 — Winebow NY" }, outputs: { category: "PO", confidence: 0.96 }, confidence: 0.96, sku_id: null, sku: null },
  { workflow_id: "wf-sync-017", thread_id: null, timestamp: toISO(daysAgo(5)), agent: "data_sync", action: "winedirect_sync", reasoning: "Scheduled sync completed. All positions current. UFRed250 inventory at WH01 adjusted +25 units (inventory count correction).", inputs: { source: "WineDirect ANWD" }, outputs: { skus_updated: 4, adjustments: 1 }, confidence: 1.0, sku_id: null, sku: null },

  { workflow_id: "wf-monitor-018", thread_id: null, timestamp: toISO(daysAgo(6)), agent: "inventory_monitor", action: "daily_summary", reasoning: "Daily summary: All metrics stable. UFCha250 DOH at 12 days (below warning threshold). UFBub250 received replenishment, now at 2,500 units.", inputs: {}, outputs: { critical: 0, warning: 2, healthy: 1, overstocked: 1 }, confidence: 0.99, sku_id: null, sku: null },
  { workflow_id: "wf-forecast-019", thread_id: null, timestamp: toISO(daysAgo(7)), agent: "demand_forecaster", action: "generate_forecast", reasoning: "Weekly batch forecast for all SKUs. Valentine's Day uplift for UFRos250 being captured by model. Seasonal decomposition showing clear weekly cycle for UFBub250.", inputs: { skus: 4 }, outputs: { avg_mape: 0.107 }, confidence: 0.88, sku_id: null, sku: null },
]

export function getDemoAuditLogs(params?: {
  page?: number
  page_size?: number
}): AuditLogListResponse {
  const page = params?.page ?? 1
  const pageSize = params?.page_size ?? 25
  const items: AuditLog[] = AUDIT_ENTRIES.map((entry, idx) => ({
    ...entry,
    id: fakeUUID(42, idx),
    created_at: entry.timestamp,
  }))

  const start = (page - 1) * pageSize
  const paged = items.slice(start, start + pageSize)

  return {
    items: paged,
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
  }
}

// ── Email Review Queue ───────────────────────────────────────────────

const DEMO_EMAILS: EmailClassification[] = [
  {
    id: fakeUUID(100, 1),
    message_id: "msg-rndc-po-4521",
    thread_id: "thr-rndc-4521",
    subject: "PO #4521 — RNDC California February Order",
    sender: "orders@rndc.com",
    recipient: "purchasing@unefemmewines.com",
    received_at: toISO(hoursAgo(2)),
    category: "PO",
    confidence: 0.94,
    reasoning: "Subject line contains 'PO #' pattern. Sender domain (rndc.com) matches known distributor. PDF attachment matches purchase order template.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "PO_4521_RNDC_CA.pdf",
    processing_time_ms: 234,
    ollama_used: false,
    created_at: toISO(hoursAgo(2)),
    updated_at: toISO(hoursAgo(2)),
  },
  {
    id: fakeUUID(100, 2),
    message_id: "msg-freight-bol-89012",
    thread_id: "thr-freight-89012",
    subject: "BOL — Shipment #TRK-89012 Departed Napa Warehouse",
    sender: "dispatch@napafreight.com",
    recipient: "logistics@unefemmewines.com",
    received_at: toISO(hoursAgo(4)),
    category: "BOL",
    confidence: 0.91,
    reasoning: "Subject explicitly mentions 'BOL' and contains tracking number. Sender is known freight carrier. Attachment is a standard bill of lading PDF.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "BOL_TRK89012.pdf",
    processing_time_ms: 189,
    ollama_used: false,
    created_at: toISO(hoursAgo(4)),
    updated_at: toISO(hoursAgo(4)),
  },
  {
    id: fakeUUID(100, 3),
    message_id: "msg-napa-inv-0342",
    thread_id: "thr-napa-inv-0342",
    subject: "Invoice INV-2026-0342 — Napa Bottling Co.",
    sender: "accounting@napabottling.com",
    recipient: "ap@unefemmewines.com",
    received_at: toISO(hoursAgo(6)),
    category: "INVOICE",
    confidence: 0.88,
    reasoning: "Subject contains 'Invoice' keyword with standard numbering. Sender matches known vendor (Napa Bottling Co.). Amount $12,600 matches open PO for UFCha250.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "INV-2026-0342.pdf",
    processing_time_ms: 312,
    ollama_used: false,
    created_at: toISO(hoursAgo(6)),
    updated_at: toISO(hoursAgo(6)),
  },
  {
    id: fakeUUID(100, 4),
    message_id: "msg-sgz-po-7890",
    thread_id: "thr-sgz-7890",
    subject: "Southern Glazers — PO #SGZ-7890 Wine Order",
    sender: "buyer@southernglazers.com",
    recipient: "sales@unefemmewines.com",
    received_at: toISO(hoursAgo(8)),
    category: "PO",
    confidence: 0.92,
    reasoning: "Contains 'PO #' identifier. Southern Glazers is a known distributor. Body references UFBub250 and UFRos250 with quantities.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "SGZ_PO_7890.xlsx",
    processing_time_ms: 276,
    ollama_used: false,
    created_at: toISO(hoursAgo(8)),
    updated_at: toISO(hoursAgo(8)),
  },
  {
    id: fakeUUID(100, 5),
    message_id: "msg-winebow-alloc",
    thread_id: "thr-winebow-alloc",
    subject: "RE: Spring allocation availability?",
    sender: "mike.chen@winebow.com",
    recipient: "sarah@unefemmewines.com",
    received_at: toISO(hoursAgo(10)),
    category: "GENERAL",
    confidence: 0.68,
    reasoning: "Inquiry about product availability for spring season. No purchase order, invoice, or shipping document attached. However, could lead to future PO. Flagged for review due to lower confidence.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: false,
    attachment_names: "",
    processing_time_ms: 445,
    ollama_used: false,
    created_at: toISO(hoursAgo(10)),
    updated_at: toISO(hoursAgo(10)),
  },
  {
    id: fakeUUID(100, 6),
    message_id: "msg-pacific-inv-1198",
    thread_id: "thr-pacific-1198",
    subject: "Payment Reminder: Invoice #PC-1198 Past Due",
    sender: "ar@pacificcoastsupplies.com",
    recipient: "ap@unefemmewines.com",
    received_at: toISO(hoursAgo(14)),
    category: "INVOICE",
    confidence: 0.85,
    reasoning: "Subject mentions 'Invoice' and 'Past Due'. From known vendor Pacific Coast Supplies. This appears to be a payment reminder for an existing invoice rather than a new invoice.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "PC-1198_reminder.pdf",
    processing_time_ms: 198,
    ollama_used: false,
    created_at: toISO(hoursAgo(14)),
    updated_at: toISO(hoursAgo(14)),
  },
  {
    id: fakeUUID(100, 7),
    message_id: "msg-bol-la-warehouse",
    thread_id: "thr-bol-la-45",
    subject: "Delivery Confirmation — LA Distribution Center",
    sender: "receiving@ladistro.com",
    recipient: "logistics@unefemmewines.com",
    received_at: toISO(hoursAgo(18)),
    category: "BOL",
    confidence: 0.79,
    reasoning: "Delivery confirmation with pallet count and receiving details. Functions as a BOL equivalent. Lower confidence because subject doesn't explicitly say 'BOL'.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "delivery_receipt_LA_020926.pdf",
    processing_time_ms: 267,
    ollama_used: false,
    created_at: toISO(hoursAgo(18)),
    updated_at: toISO(hoursAgo(18)),
  },
  {
    id: fakeUUID(100, 8),
    message_id: "msg-reyes-po-2200",
    thread_id: "thr-reyes-2200",
    subject: "Reyes Beer Division — Purchase Order #RBD-2200",
    sender: "procurement@reyesbeer.com",
    recipient: "sales@unefemmewines.com",
    received_at: toISO(hoursAgo(22)),
    category: "PO",
    confidence: 0.96,
    reasoning: "Clear purchase order from Reyes Beer Division. Subject contains 'Purchase Order' with ID. Attached Excel spreadsheet with line items for UFRed250 and UFBub250.",
    needs_review: false,
    reviewed: true,
    reviewed_by: "sarah",
    reviewed_at: toISO(hoursAgo(20)),
    corrected_category: null,
    has_attachments: true,
    attachment_names: "RBD_PO_2200.xlsx",
    processing_time_ms: 156,
    ollama_used: false,
    created_at: toISO(hoursAgo(22)),
    updated_at: toISO(hoursAgo(20)),
  },
  {
    id: fakeUUID(100, 9),
    message_id: "msg-rndc-report",
    thread_id: "thr-rndc-weekly",
    subject: "RNDC Weekly Depletion Report — Week Ending 02/07/2026",
    sender: "reports@rndc.com",
    recipient: "analytics@unefemmewines.com",
    received_at: toISO(hoursAgo(26)),
    category: "GENERAL",
    confidence: 0.61,
    reasoning: "Weekly depletion report from RNDC. Contains data but isn't a PO, invoice, or BOL. Could be classified as a data file. Low confidence — may be better categorized as a custom 'REPORT' type.",
    needs_review: true,
    reviewed: false,
    reviewed_by: null,
    reviewed_at: null,
    corrected_category: null,
    has_attachments: true,
    attachment_names: "rndc_depletion_wk06_2026.csv",
    processing_time_ms: 389,
    ollama_used: false,
    created_at: toISO(hoursAgo(26)),
    updated_at: toISO(hoursAgo(26)),
  },
  {
    id: fakeUUID(100, 10),
    message_id: "msg-golden-state-inv",
    thread_id: "thr-golden-inv-87",
    subject: "Golden State Packaging — Invoice for Label Print Run",
    sender: "billing@goldenstatepkg.com",
    recipient: "ap@unefemmewines.com",
    received_at: toISO(hoursAgo(30)),
    category: "INVOICE",
    confidence: 0.90,
    reasoning: "Invoice from Golden State Packaging for label printing services. Known vendor. Amount $2,340 for 50,000 bottle labels.",
    needs_review: false,
    reviewed: true,
    reviewed_by: "mike",
    reviewed_at: toISO(hoursAgo(28)),
    corrected_category: null,
    has_attachments: true,
    attachment_names: "GS_INV_87_labels.pdf",
    processing_time_ms: 201,
    ollama_used: false,
    created_at: toISO(hoursAgo(30)),
    updated_at: toISO(hoursAgo(28)),
  },
  {
    id: fakeUUID(100, 11),
    message_id: "msg-freight-bol-88990",
    thread_id: "thr-freight-88990",
    subject: "Shipment Manifest — Container #MSKU-4427891",
    sender: "operations@centralfreight.com",
    recipient: "logistics@unefemmewines.com",
    received_at: toISO(hoursAgo(36)),
    category: "BOL",
    confidence: 0.83,
    reasoning: "Shipment manifest with container number for NY warehouse delivery. Includes pallet breakdown by SKU. Classified as BOL based on shipping context.",
    needs_review: false,
    reviewed: true,
    reviewed_by: "sarah",
    reviewed_at: toISO(hoursAgo(34)),
    corrected_category: null,
    has_attachments: true,
    attachment_names: "manifest_MSKU4427891.pdf, packing_list.xlsx",
    processing_time_ms: 342,
    ollama_used: false,
    created_at: toISO(hoursAgo(36)),
    updated_at: toISO(hoursAgo(34)),
  },
  {
    id: fakeUUID(100, 12),
    message_id: "msg-winedirect-notif",
    thread_id: "thr-winedirect-api",
    subject: "WineDirect API: HTTPS Migration Reminder (Feb 16 Deadline)",
    sender: "api-support@winedirect.com",
    recipient: "tech@unefemmewines.com",
    received_at: toISO(hoursAgo(48)),
    category: "GENERAL",
    confidence: 0.97,
    reasoning: "Technical notification about API migration deadline. Not a business document (PO/BOL/Invoice). Clearly general correspondence about infrastructure.",
    needs_review: false,
    reviewed: true,
    reviewed_by: "sarah",
    reviewed_at: toISO(hoursAgo(46)),
    corrected_category: null,
    has_attachments: false,
    attachment_names: "",
    processing_time_ms: 123,
    ollama_used: false,
    created_at: toISO(hoursAgo(48)),
    updated_at: toISO(hoursAgo(46)),
  },
]

export function getDemoReviewQueue(params?: {
  category?: EmailCategory
  page?: number
  page_size?: number
}): ReviewQueueResponse {
  let items = DEMO_EMAILS.filter((e) => e.needs_review && !e.reviewed)
  if (params?.category) {
    items = items.filter((e) => e.category === params.category)
  }
  const page = params?.page ?? 1
  const pageSize = params?.page_size ?? 25
  const start = (page - 1) * pageSize

  return {
    items: items.slice(start, start + pageSize),
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: Math.ceil(items.length / pageSize),
  }
}

export function getDemoReviewStats(): ReviewQueueStats {
  const pending = DEMO_EMAILS.filter((e) => e.needs_review && !e.reviewed)
  const reviewed = DEMO_EMAILS.filter((e) => e.reviewed)
  const allConfidences = DEMO_EMAILS.map((e) => e.confidence)
  const avg = allConfidences.reduce((a, b) => a + b, 0) / allConfidences.length

  const byCategory: Record<string, number> = {}
  for (const e of pending) {
    byCategory[e.category] = (byCategory[e.category] ?? 0) + 1
  }

  return {
    pending_review: pending.length,
    reviewed_today: 12,
    total_reviewed: 247,
    avg_confidence: +avg.toFixed(2),
    by_category: byCategory,
  }
}

// ── Procurement Approvals ────────────────────────────────────────────

export interface ProcurementOrder {
  id: string
  sku: string
  sku_label: string
  current_inventory: number
  doh_t30: number
  recommended_quantity: number
  vendor: string
  unit_price: number
  order_value: number
  approval_level: "auto" | "manager" | "executive"
  approval_status: "pending_review" | "approved" | "rejected"
  urgency: "critical" | "high" | "medium" | "low"
  reviewer: string | null
  created_at: string
  reasoning: string
}

export function getDemoProcurementOrders(): ProcurementOrder[] {
  return [
    {
      id: fakeUUID(200, 1),
      sku: "UFCha250",
      sku_label: "Chardonnay",
      current_inventory: 520,
      doh_t30: 8,
      recommended_quantity: 3000,
      vendor: "Napa Bottling Co.",
      unit_price: 4.20,
      order_value: 12600,
      approval_level: "executive",
      approval_status: "pending_review",
      urgency: "critical",
      reviewer: null,
      created_at: toISO(hoursAgo(4)),
      reasoning: "Critical stock level — 8 days remaining at current burn rate of 65 units/day. Order covers 6 weeks of projected demand plus 15% safety buffer. Executive approval required (>$10K).",
    },
    {
      id: fakeUUID(200, 2),
      sku: "UFRos250",
      sku_label: "Sparkling Ros\u00e9",
      current_inventory: 1100,
      doh_t30: 20,
      recommended_quantity: 2500,
      vendor: "Pacific Coast Supplies",
      unit_price: 3.50,
      order_value: 8750,
      approval_level: "manager",
      approval_status: "pending_review",
      urgency: "high",
      reviewer: null,
      created_at: toISO(hoursAgo(5)),
      reasoning: "Demand accelerating — 30-day depletion rate 38% above 90-day average. Preemptive reorder to prevent stockout. 5-week coverage at accelerated rate. Manager approval required ($5K-$10K).",
    },
    {
      id: fakeUUID(200, 3),
      sku: "UFBub250",
      sku_label: "Sparkling Brut",
      current_inventory: 2350,
      doh_t30: 47,
      recommended_quantity: 1200,
      vendor: "Napa Bottling Co.",
      unit_price: 3.80,
      order_value: 4560,
      approval_level: "auto",
      approval_status: "approved",
      urgency: "low",
      reviewer: null,
      created_at: toISO(daysAgo(3)),
      reasoning: "Routine restock. Current levels healthy but approaching 30-day reorder window. Standard 4-week coverage order. Auto-approved (confidence 92%, value <$5K).",
    },
    {
      id: fakeUUID(200, 4),
      sku: "UFCha250",
      sku_label: "Chardonnay",
      current_inventory: 750,
      doh_t30: 11,
      recommended_quantity: 2000,
      vendor: "Pacific Coast Supplies",
      unit_price: 4.10,
      order_value: 8200,
      approval_level: "manager",
      approval_status: "approved",
      urgency: "high",
      reviewer: "Sarah",
      created_at: toISO(daysAgo(7)),
      reasoning: "Approved by Sarah (Supply Chain Manager) on Feb 2. Shipment received Feb 5 — 1,800 units delivered to WH01. Remaining 200 units backordered, ETA Feb 12.",
    },
    {
      id: fakeUUID(200, 5),
      sku: "UFRed250",
      sku_label: "Red Blend",
      current_inventory: 1800,
      doh_t30: 90,
      recommended_quantity: 500,
      vendor: "Golden State Packaging",
      unit_price: 3.60,
      order_value: 1800,
      approval_level: "auto",
      approval_status: "rejected",
      urgency: "low",
      reviewer: "Sarah",
      created_at: toISO(daysAgo(5)),
      reasoning: "Rejected — SKU is currently overstocked at 90 DOH. Additional inventory would increase holding costs. Recommend deferring until DOH drops below 60 days.",
    },
  ]
}

// ── Recent Upload History ────────────────────────────────────────────

export interface UploadHistoryEntry {
  id: string
  filename: string
  distributor: string
  uploaded_at: string
  uploaded_by: string
  total_rows: number
  success_count: number
  error_count: number
  status: "completed" | "partial" | "failed"
}

export function getDemoUploadHistory(): UploadHistoryEntry[] {
  return [
    {
      id: fakeUUID(300, 1),
      filename: "rndc_depletions_feb_2026.csv",
      distributor: "RNDC",
      uploaded_at: toISO(hoursAgo(12)),
      uploaded_by: "Sarah",
      total_rows: 142,
      success_count: 139,
      error_count: 3,
      status: "partial",
    },
    {
      id: fakeUUID(300, 2),
      filename: "sgz_weekly_020526.xlsx",
      distributor: "Southern Glazers",
      uploaded_at: toISO(daysAgo(2)),
      uploaded_by: "Mike",
      total_rows: 87,
      success_count: 85,
      error_count: 2,
      status: "partial",
    },
    {
      id: fakeUUID(300, 3),
      filename: "winebow_jan_depletions.csv",
      distributor: "Winebow",
      uploaded_at: toISO(daysAgo(5)),
      uploaded_by: "Sarah",
      total_rows: 64,
      success_count: 64,
      error_count: 0,
      status: "completed",
    },
    {
      id: fakeUUID(300, 4),
      filename: "rndc_depletions_jan_wk4.csv",
      distributor: "RNDC",
      uploaded_at: toISO(daysAgo(8)),
      uploaded_by: "Sarah",
      total_rows: 156,
      success_count: 156,
      error_count: 0,
      status: "completed",
    },
    {
      id: fakeUUID(300, 5),
      filename: "sgz_monthly_jan_2026.xlsx",
      distributor: "Southern Glazers",
      uploaded_at: toISO(daysAgo(12)),
      uploaded_by: "Mike",
      total_rows: 312,
      success_count: 308,
      error_count: 4,
      status: "partial",
    },
  ]
}
