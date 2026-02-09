"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { TrendingUp, TrendingDown, Minus } from "lucide-react"
import { cn } from "@/lib/utils"
import type { SKUMetrics } from "@/lib/api-types"

const skuLabels: Record<string, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

interface VelocityTrendsProps {
  skus: SKUMetrics[]
}

export function VelocityTrends({ skus }: VelocityTrendsProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          Velocity Trends (30d vs 90d)
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {skus.map((sku) => {
            const trend = sku.velocity_trend.velocity_trend_dep
            const isAccelerating = trend !== null && trend > 1.05
            const isDecelerating = trend !== null && trend < 0.95
            const rate30 = sku.velocity_trend.daily_rate_30d_dep
            const rate90 = sku.velocity_trend.daily_rate_90d_dep

            return (
              <div
                key={sku.sku}
                className="flex items-center justify-between rounded-lg border border-border px-4 py-3"
              >
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {skuLabels[sku.sku] ?? sku.sku}
                  </p>
                  <p className="font-data text-xs text-muted-foreground">
                    {rate30 !== null ? rate30.toFixed(1) : "—"} / day (30d)
                    {rate90 !== null && (
                      <span className="ml-1 text-text-muted">
                        vs {rate90.toFixed(1)} (90d)
                      </span>
                    )}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  {isAccelerating ? (
                    <TrendingUp className="h-4 w-4 text-rose-500" />
                  ) : isDecelerating ? (
                    <TrendingDown className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <Minus className="h-4 w-4 text-muted-foreground" />
                  )}
                  <span
                    className={cn(
                      "font-data text-sm font-medium",
                      isAccelerating
                        ? "text-rose-500"
                        : isDecelerating
                          ? "text-emerald-500"
                          : "text-muted-foreground"
                    )}
                  >
                    {trend !== null ? `${trend.toFixed(2)}x` : "—"}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
