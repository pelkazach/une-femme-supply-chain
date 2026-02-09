"use client"

import { use } from "react"
import { useQuery } from "@tanstack/react-query"
import { getSkuMetrics, getDepletionEvents } from "@/lib/api-client"
import { getDOHStatus } from "@/components/shared/kpi-card"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ChartSkeleton } from "@/components/shared/skeletons"
import { cn } from "@/lib/utils"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { useMemo } from "react"
import { useQueryState, parseAsString } from "nuqs"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry, themeQuartz } from "ag-grid-community"
import type { ColDef } from "ag-grid-community"
import type { DepletionEvent } from "@/lib/api-types"
import { TableSkeleton } from "@/components/shared/skeletons"

ModuleRegistry.registerModules([AllCommunityModule])

const skuLabels: Record<string, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

type RangeOption = "30d" | "60d" | "90d"

function daysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().split("T")[0]
}

const rangeDays: Record<RangeOption, number> = {
  "30d": 30,
  "60d": 60,
  "90d": 90,
}

export default function InventoryDetailPage({
  params,
}: {
  params: Promise<{ sku: string }>
}) {
  const { sku } = use(params)
  const [range, setRange] = useQueryState(
    "range",
    parseAsString.withDefault("30d")
  )
  const [warehouse] = useQueryState("warehouse", parseAsString)
  const [distributor] = useQueryState("distributor", parseAsString)

  const validRange = (["30d", "60d", "90d"] as const).includes(
    range as RangeOption
  )
    ? (range as RangeOption)
    : "30d"

  const startDate = daysAgo(rangeDays[validRange])
  const endDate = new Date().toISOString().split("T")[0]

  const metricsParams = {
    ...(warehouse ? { warehouse_code: warehouse } : {}),
    ...(distributor ? { distributor_name: distributor } : {}),
  }

  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ["sku-metrics", sku, metricsParams],
    queryFn: () => getSkuMetrics(sku, metricsParams),
    staleTime: 30_000,
    refetchInterval: 30_000,
  })

  const { data: depletionData, isLoading: depletionLoading } = useQuery({
    queryKey: ["depletion-events", sku, validRange, warehouse, distributor],
    queryFn: () =>
      getDepletionEvents({
        sku,
        start_date: startDate,
        end_date: endDate,
      }),
    staleTime: 60_000,
    refetchInterval: 120_000,
  })

  const gridTheme = themeQuartz.withParams({
    backgroundColor: "transparent",
    foregroundColor: "var(--color-foreground)",
    borderColor: "var(--color-border)",
    headerBackgroundColor: "var(--color-surface)",
    rowHoverColor: "var(--color-accent)",
    fontFamily: "var(--font-sans)",
    fontSize: 13,
  })

  const columnDefs = useMemo<ColDef<DepletionEvent>[]>(
    () => [
      {
        field: "event_time",
        headerName: "Date",
        sortable: true,
        valueFormatter: (p) =>
          p.value ? new Date(p.value as string).toLocaleDateString() : "",
        flex: 1,
      },
      {
        field: "quantity",
        headerName: "Quantity",
        sortable: true,
        flex: 1,
      },
      {
        field: "order_id",
        headerName: "Order ID",
        sortable: true,
        flex: 1,
      },
      {
        field: "customer",
        headerName: "Customer",
        sortable: true,
        flex: 1.5,
      },
      {
        field: "warehouse",
        headerName: "Warehouse",
        sortable: true,
        flex: 1,
      },
    ],
    []
  )

  const label = skuLabels[sku] ?? sku
  const doh = metrics?.doh.doh_t30 ?? null
  const status = getDOHStatus(doh)

  // Build chart data from depletion events (aggregate by day)
  const chartData: { date: string; quantity: number }[] = []
  if (depletionData) {
    const byDay = new Map<string, number>()
    for (const event of depletionData.events) {
      const day = event.event_time.split("T")[0]
      byDay.set(day, (byDay.get(day) ?? 0) + event.quantity)
    }
    const sorted = Array.from(byDay.entries()).sort(([a], [b]) =>
      a.localeCompare(b)
    )
    for (const [date, quantity] of sorted) {
      chartData.push({ date, quantity })
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading text-2xl font-semibold text-foreground">
            {label}
          </h2>
          <p className="text-sm text-muted-foreground">{sku}</p>
        </div>
        <StatusBadge status={status} doh={doh} />
      </div>

      {/* Metrics summary */}
      {metricsLoading ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <div className="h-4 w-16 animate-pulse rounded bg-accent" />
                <div className="mt-2 h-6 w-12 animate-pulse rounded bg-accent" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : metrics ? (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground">Current Inventory</p>
              <p className="font-data text-xl font-semibold text-foreground">
                {metrics.doh.current_inventory.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground">DOH (T30)</p>
              <p className="font-data text-xl font-semibold text-foreground">
                {doh !== null ? Math.round(doh) : "—"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground">DOH (T90)</p>
              <p className="font-data text-xl font-semibold text-foreground">
                {metrics.doh.doh_t90 !== null
                  ? Math.round(metrics.doh.doh_t90)
                  : "—"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <p className="text-xs text-muted-foreground">30d Depletion</p>
              <p className="font-data text-xl font-semibold text-foreground">
                {metrics.doh.depletion_30d.toLocaleString()}
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Area chart */}
      {depletionLoading ? (
        <ChartSkeleton />
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Depletion Events Over Time
            </CardTitle>
            <div className="flex gap-1">
              {(["30d", "60d", "90d"] as RangeOption[]).map((r) => (
                <Button
                  key={r}
                  variant={validRange === r ? "default" : "ghost"}
                  size="sm"
                  onClick={() => setRange(r)}
                  className={cn(
                    "h-7 text-xs",
                    validRange === r && "bg-gold text-primary-foreground hover:bg-gold-hover"
                  )}
                >
                  {r}
                </Button>
              ))}
            </div>
          </CardHeader>
          <CardContent>
            {chartData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="depGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="0%"
                          stopColor="var(--color-gold)"
                          stopOpacity={0.3}
                        />
                        <stop
                          offset="100%"
                          stopColor="var(--color-gold)"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      vertical={false}
                      stroke="var(--color-border)"
                    />
                    <XAxis
                      dataKey="date"
                      tick={{
                        fill: "var(--color-muted-foreground)",
                        fontSize: 11,
                      }}
                      axisLine={false}
                      tickLine={false}
                      tickFormatter={(d: string) => {
                        const parts = d.split("-")
                        return `${parts[1]}/${parts[2]}`
                      }}
                    />
                    <YAxis
                      tick={{
                        fill: "var(--color-muted-foreground)",
                        fontSize: 11,
                      }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "var(--color-surface)",
                        border: "1px solid var(--color-border)",
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelStyle={{ color: "var(--color-foreground)" }}
                      itemStyle={{ color: "var(--color-foreground)" }}
                    />
                    <Area
                      type="monotone"
                      dataKey="quantity"
                      stroke="var(--color-gold)"
                      strokeWidth={2}
                      fill="url(#depGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No depletion events in this time range
              </p>
            )}
          </CardContent>
        </Card>
      )}
      {/* Depletion events table */}
      {depletionLoading ? (
        <TableSkeleton rows={8} />
      ) : (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Depletion Events
            </CardTitle>
          </CardHeader>
          <CardContent>
            {depletionData && depletionData.events.length > 0 ? (
              <div className="h-[400px]">
                <AgGridReact<DepletionEvent>
                  theme={gridTheme}
                  rowData={depletionData.events}
                  columnDefs={columnDefs}
                  defaultColDef={{
                    filter: true,
                    resizable: true,
                  }}
                  pagination
                  paginationPageSize={20}
                />
              </div>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                No depletion events in this time range
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
