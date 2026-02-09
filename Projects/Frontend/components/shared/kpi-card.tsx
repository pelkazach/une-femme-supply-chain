"use client"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown, Minus } from "lucide-react"
import {
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts"

export type DOHStatus = "critical" | "warning" | "healthy" | "overstocked" | "no-data"

export interface KpiCardProps {
  label: string
  value: string | number
  subtitle?: string
  delta?: number | null
  deltaLabel?: string
  status?: DOHStatus
  sparklineData?: { value: number }[]
}

const statusConfig: Record<DOHStatus, { label: string; className: string; dotClass: string }> = {
  critical: {
    label: "Critical",
    className: "bg-red-500/10 text-red-500",
    dotClass: "bg-red-500",
  },
  warning: {
    label: "Warning",
    className: "bg-amber-500/10 text-amber-500",
    dotClass: "bg-amber-500",
  },
  healthy: {
    label: "Healthy",
    className: "bg-green-500/10 text-green-500",
    dotClass: "bg-green-500",
  },
  overstocked: {
    label: "Overstocked",
    className: "bg-blue-500/10 text-blue-500",
    dotClass: "bg-blue-500",
  },
  "no-data": {
    label: "No Data",
    className: "bg-muted text-muted-foreground",
    dotClass: "bg-muted-foreground",
  },
}

const statusColorMap: Record<DOHStatus, string> = {
  critical: "#ef4444",
  warning: "#f59e0b",
  healthy: "#22c55e",
  overstocked: "#3b82f6",
  "no-data": "#6b6b6b",
}

export function getDOHStatus(doh: number | null): DOHStatus {
  if (doh === null) return "no-data"
  if (doh < 14) return "critical"
  if (doh < 30) return "warning"
  if (doh <= 90) return "healthy"
  return "overstocked"
}

export function KpiCard({
  label,
  value,
  subtitle,
  delta,
  deltaLabel,
  status = "no-data",
  sparklineData,
}: KpiCardProps) {
  const cfg = statusConfig[status]
  const sparkColor = statusColorMap[status]

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {label}
        </CardTitle>
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
            cfg.className
          )}
        >
          <span className={cn("h-1.5 w-1.5 rounded-full", cfg.dotClass)} />
          {cfg.label}
        </span>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="font-data text-2xl font-semibold text-foreground">
            {typeof value === "number" ? value.toLocaleString() : value}
          </p>
          {subtitle && (
            <p className="text-xs text-muted-foreground">{subtitle}</p>
          )}
        </div>

        {delta !== undefined && delta !== null && (
          <div className="flex items-center gap-1 text-xs">
            {delta > 0 ? (
              <TrendingUp className="h-3 w-3 text-green-500" />
            ) : delta < 0 ? (
              <TrendingDown className="h-3 w-3 text-red-500" />
            ) : (
              <Minus className="h-3 w-3 text-muted-foreground" />
            )}
            <span
              className={cn(
                "font-data font-medium",
                delta > 0
                  ? "text-green-500"
                  : delta < 0
                    ? "text-red-500"
                    : "text-muted-foreground"
              )}
            >
              {delta > 0 ? "+" : ""}
              {delta.toFixed(1)}%
            </span>
            {deltaLabel && (
              <span className="text-muted-foreground">{deltaLabel}</span>
            )}
          </div>
        )}

        {sparklineData && sparklineData.length > 0 && (
          <div className="h-10">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparklineData}>
                <defs>
                  <linearGradient id={`grad-${label}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={sparkColor} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={sparkColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke={sparkColor}
                  strokeWidth={1.5}
                  fill={`url(#grad-${label})`}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
