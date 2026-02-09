"use client"

import Link from "next/link"
import { useMetrics } from "@/lib/hooks/use-metrics"
import { useAuditLogs } from "@/lib/hooks/use-audit-logs"
import { useReviewStats } from "@/lib/hooks/use-review-stats"
import { KpiCard, getDOHStatus } from "@/components/shared/kpi-card"
import { ShipDepChart } from "@/components/shared/ship-dep-chart"
import { VelocityTrends } from "@/components/shared/velocity-trends"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { KpiCardSkeleton, ChartSkeleton } from "@/components/shared/skeletons"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertTriangle, Mail, ShoppingCart, ArrowRight } from "lucide-react"

const skuLabels: Record<string, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

export default function DashboardPage() {
  const { data, isLoading, error } = useMetrics()
  const { data: auditData, isLoading: auditLoading } = useAuditLogs({ page_size: 5 })
  const { data: reviewStats, isLoading: reviewLoading } = useReviewStats()

  if (error) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <AlertTriangle className="mx-auto h-10 w-10 text-destructive" />
          <p className="mt-3 text-lg font-medium text-foreground">
            Failed to load metrics
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Could not connect to the backend API. Check your connection.
          </p>
        </div>
      </div>
    )
  }

  const criticalSkus =
    data?.skus.filter(
      (s) => s.doh.doh_t30 !== null && s.doh.doh_t30 < 14
    ) ?? []

  return (
    <div className="space-y-6">
      {/* Alert banner */}
      {criticalSkus.length > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-red-500" />
          <p className="text-sm text-red-400">
            <span className="font-medium">Stock alert:</span>{" "}
            {criticalSkus
              .map(
                (s) =>
                  `${skuLabels[s.sku] ?? s.sku} (${Math.round(s.doh.doh_t30!)}d)`
              )
              .join(", ")}{" "}
            below 14-day threshold
          </p>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <KpiCardSkeleton key={i} />
            ))
          : data?.skus.map((sku) => {
              const status = getDOHStatus(sku.doh.doh_t30)
              const doh = sku.doh.doh_t30

              return (
                <KpiCard
                  key={sku.sku}
                  label={skuLabels[sku.sku] ?? sku.sku}
                  value={sku.doh.current_inventory}
                  showCases
                  subtitle={
                    doh !== null
                      ? `${Math.round(doh)} days on hand (T30)`
                      : "No DOH data"
                  }
                  status={status}
                />
              )
            })}
      </div>

      {/* Charts row */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton height="h-48" />
        </div>
      ) : data && data.skus.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ShipDepChart skus={data.skus} />
          <VelocityTrends skus={data.skus} />
        </div>
      ) : null}

      {/* Activity feed & Quick actions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Recent activity */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Recent Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            {auditLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-8 w-8 rounded-full" />
                    <div className="flex-1 space-y-1">
                      <Skeleton className="h-3 w-48" />
                      <Skeleton className="h-3 w-32" />
                    </div>
                  </div>
                ))}
              </div>
            ) : auditData && auditData.items.length > 0 ? (
              <ul className="space-y-3">
                {auditData.items.map((entry) => (
                  <li
                    key={entry.id}
                    className="flex items-start gap-3 text-sm"
                  >
                    <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-elevated text-xs font-medium text-muted-foreground">
                      {entry.agent.charAt(0).toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-foreground">
                        <span className="font-medium">{entry.agent}</span>{" "}
                        {entry.action}
                        {entry.sku && (
                          <span className="font-data ml-1 text-muted-foreground">
                            ({entry.sku})
                          </span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-4 text-center text-sm text-muted-foreground">
                No recent activity
              </p>
            )}
          </CardContent>
        </Card>

        {/* Quick actions */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Quick Actions
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {reviewLoading ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full rounded-lg" />
                <Skeleton className="h-12 w-full rounded-lg" />
              </div>
            ) : (
              <>
                <Link
                  href="/review"
                  className="flex items-center justify-between rounded-lg border border-border px-4 py-3 transition-colors hover:bg-accent"
                >
                  <div className="flex items-center gap-3">
                    <Mail className="h-4 w-4 text-gold" />
                    <span className="text-sm text-foreground">
                      Pending Reviews
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-data text-sm font-medium text-foreground">
                      {reviewStats?.pending_review ?? 0}
                    </span>
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  </div>
                </Link>
                <Link
                  href="/approvals"
                  className="flex items-center justify-between rounded-lg border border-border px-4 py-3 transition-colors hover:bg-accent"
                >
                  <div className="flex items-center gap-3">
                    <ShoppingCart className="h-4 w-4 text-gold" />
                    <span className="text-sm text-foreground">
                      Pending Approvals
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                  </div>
                </Link>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Empty state */}
      {data && data.skus.length === 0 && (
        <div className="py-16 text-center">
          <p className="text-lg font-medium text-foreground">No data yet</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload distributor files or sync WineDirect to populate metrics.
          </p>
        </div>
      )}
    </div>
  )
}
