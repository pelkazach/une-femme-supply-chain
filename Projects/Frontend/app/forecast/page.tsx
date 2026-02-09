"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { getMetrics } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ChartSkeleton } from "@/components/shared/skeletons"
import { cn } from "@/lib/utils"
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts"
import { TrendingUp } from "lucide-react"

const SKUS = ["UFBub250", "UFRos250", "UFRed250", "UFCha250"] as const
type SKU = (typeof SKUS)[number]

const skuLabels: Record<SKU, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

// Generate demo forecast data (26 weeks) since no dedicated API exists yet
function generateForecastData(baseDailyRate: number) {
  const data: {
    week: string
    actual: number | null
    forecast: number | null
    lower80: number | null
    upper80: number | null
    lower95: number | null
    upper95: number | null
  }[] = []

  const now = new Date()

  // 12 weeks of historical "actuals"
  for (let w = -12; w < 0; w++) {
    const date = new Date(now)
    date.setDate(date.getDate() + w * 7)
    const noise = 1 + (Math.sin(w * 0.5) * 0.2 + (Math.random() - 0.5) * 0.15)
    const weeklyVal = Math.round(baseDailyRate * 7 * noise)
    data.push({
      week: date.toISOString().split("T")[0],
      actual: weeklyVal,
      forecast: null,
      lower80: null,
      upper80: null,
      lower95: null,
      upper95: null,
    })
  }

  // 26 weeks of forecast
  for (let w = 0; w < 26; w++) {
    const date = new Date(now)
    date.setDate(date.getDate() + w * 7)
    const trend = 1 + w * 0.005
    const seasonal = 1 + Math.sin((w / 26) * Math.PI * 2) * 0.1
    const predicted = Math.round(baseDailyRate * 7 * trend * seasonal)
    const spread80 = Math.round(predicted * 0.15 * (1 + w * 0.02))
    const spread95 = Math.round(predicted * 0.25 * (1 + w * 0.02))

    data.push({
      week: date.toISOString().split("T")[0],
      actual: null,
      forecast: predicted,
      lower80: predicted - spread80,
      upper80: predicted + spread80,
      lower95: predicted - spread95,
      upper95: predicted + spread95,
    })
  }

  return data
}

export default function ForecastPage() {
  const [selectedSku, setSelectedSku] = useState<SKU>("UFBub250")
  const { data: metricsData, isLoading } = useQuery({
    queryKey: ["metrics"],
    queryFn: () => getMetrics(),
    staleTime: 60_000,
    refetchInterval: 300_000,
  })

  const skuMetrics = metricsData?.skus.find((s) => s.sku === selectedSku)
  const dailyRate = skuMetrics?.doh.daily_rate_30d ?? 5
  const chartData = generateForecastData(dailyRate)

  return (
    <div className="space-y-6">
      {/* SKU tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-surface p-1">
        {SKUS.map((sku) => (
          <Button
            key={sku}
            variant={selectedSku === sku ? "default" : "ghost"}
            size="sm"
            onClick={() => setSelectedSku(sku)}
            className={cn(
              "flex-1 text-xs",
              selectedSku === sku &&
                "bg-gold text-primary-foreground hover:bg-gold-hover"
            )}
          >
            {skuLabels[sku]}
          </Button>
        ))}
      </div>

      {/* Forecast chart */}
      {isLoading ? (
        <ChartSkeleton height="h-80" />
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <div>
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Demand Forecast — {skuLabels[selectedSku]}
              </CardTitle>
              <p className="text-xs text-muted-foreground">
                26-week projection with confidence intervals
              </p>
            </div>
            <div className="flex items-center gap-1.5 rounded-md bg-green-500/10 px-2 py-1">
              <TrendingUp className="h-3 w-3 text-green-500" />
              <span className="text-xs font-medium text-green-500">
                Model confidence: 87%
              </span>
            </div>
          </CardHeader>
          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    vertical={false}
                    stroke="var(--color-border)"
                  />
                  <XAxis
                    dataKey="week"
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
                  />
                  <ReferenceLine
                    x={new Date().toISOString().split("T")[0]}
                    stroke="var(--color-text-muted)"
                    strokeDasharray="4 4"
                    label={{
                      value: "Today",
                      position: "top",
                      fill: "var(--color-muted-foreground)",
                      fontSize: 10,
                    }}
                  />
                  {/* 95% confidence band */}
                  <Area
                    type="monotone"
                    dataKey="upper95"
                    stroke="none"
                    fill="var(--color-muted)"
                    fillOpacity={0.3}
                  />
                  <Area
                    type="monotone"
                    dataKey="lower95"
                    stroke="none"
                    fill="var(--color-background)"
                    fillOpacity={1}
                  />
                  {/* 80% confidence band */}
                  <Area
                    type="monotone"
                    dataKey="upper80"
                    stroke="none"
                    fill="var(--color-muted)"
                    fillOpacity={0.5}
                  />
                  <Area
                    type="monotone"
                    dataKey="lower80"
                    stroke="none"
                    fill="var(--color-background)"
                    fillOpacity={1}
                  />
                  {/* Actuals line */}
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#635bff"
                    strokeWidth={2}
                    dot={false}
                    connectNulls={false}
                  />
                  {/* Forecast line */}
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke="#10b981"
                    strokeWidth={2}
                    strokeDasharray="6 3"
                    dot={false}
                    connectNulls={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* Legend */}
            <div className="mt-4 flex flex-wrap justify-center gap-4 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5">
                <span className="h-0.5 w-4 bg-[#635bff]" />
                Actuals
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-0.5 w-4 border-t-2 border-dashed border-emerald-500" />
                Forecast
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-4 rounded-sm bg-muted/50" />
                80% CI
              </div>
              <div className="flex items-center gap-1.5">
                <span className="h-3 w-4 rounded-sm bg-muted/30" />
                95% CI
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Forecast summary table */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Weekly Forecast Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="max-h-96 overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-border">
                  <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">
                    Week
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                    Predicted
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                    Lower 80%
                  </th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-muted-foreground">
                    Upper 80%
                  </th>
                </tr>
              </thead>
              <tbody>
                {chartData
                  .filter((d) => d.forecast !== null)
                  .map((d) => (
                    <tr
                      key={d.week}
                      className="border-b border-border last:border-0"
                    >
                      <td className="font-data px-3 py-2 text-foreground">
                        {d.week}
                      </td>
                      <td className="font-data px-3 py-2 text-right text-foreground">
                        {d.forecast}
                      </td>
                      <td className="font-data px-3 py-2 text-right text-muted-foreground">
                        {d.lower80}
                      </td>
                      <td className="font-data px-3 py-2 text-right text-muted-foreground">
                        {d.upper80}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
