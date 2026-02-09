"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { SKUMetrics } from "@/lib/api-types"

const skuLabels: Record<string, string> = {
  UFBub250: "Brut",
  UFRos250: "Rosé",
  UFRed250: "Red",
  UFCha250: "Chard",
}

interface ShipDepChartProps {
  skus: SKUMetrics[]
}

export function ShipDepChart({ skus }: ShipDepChartProps) {
  const data = skus.map((s) => ({
    name: skuLabels[s.sku] ?? s.sku,
    "30d Ratio": s.ship_dep_ratio.ratio_30d ?? 0,
    "90d Ratio": s.ship_dep_ratio.ratio_90d ?? 0,
  }))

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Shipment : Depletion Ratio
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barGap={4} barCategoryGap="25%">
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="var(--color-border)"
              />
              <XAxis
                dataKey="name"
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "var(--color-muted-foreground)", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                domain={[0, "auto"]}
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
                formatter={(value) => typeof value === "number" ? value.toFixed(2) : String(value)}
              />
              <Legend
                wrapperStyle={{ fontSize: 12, color: "var(--color-muted-foreground)" }}
              />
              <ReferenceLine
                y={0.5}
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: "Low (0.5)",
                  position: "right",
                  fill: "#ef4444",
                  fontSize: 10,
                }}
              />
              <ReferenceLine
                y={2.0}
                stroke="#3b82f6"
                strokeDasharray="4 4"
                strokeWidth={1}
                label={{
                  value: "High (2.0)",
                  position: "right",
                  fill: "#3b82f6",
                  fontSize: 10,
                }}
              />
              <Bar
                dataKey="30d Ratio"
                fill="var(--color-gold)"
                radius={[4, 4, 0, 0]}
              />
              <Bar
                dataKey="90d Ratio"
                fill="var(--color-burgundy)"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
