"use client"

import { useMetrics } from "@/lib/hooks/use-metrics"
import { getDOHStatus } from "@/components/shared/kpi-card"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertTriangle, Bell } from "lucide-react"

const skuLabels: Record<string, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

export default function AlertsPage() {
  const { data, isLoading } = useMetrics()

  const alerts = (data?.skus ?? [])
    .filter((s) => s.doh.doh_t30 !== null && s.doh.doh_t30 < 30)
    .sort((a, b) => (a.doh.doh_t30 ?? Infinity) - (b.doh.doh_t30 ?? Infinity))

  return (
    <div className="space-y-6">
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="flex items-center gap-4 pt-6">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-32" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : alerts.length > 0 ? (
        <div className="space-y-3">
          {alerts.map((sku) => {
            const status = getDOHStatus(sku.doh.doh_t30)
            const isCritical = sku.doh.doh_t30 !== null && sku.doh.doh_t30 < 14

            return (
              <Card
                key={sku.sku}
                className={
                  isCritical ? "border-red-500/30" : "border-amber-500/20"
                }
              >
                <CardContent className="flex items-center justify-between pt-6">
                  <div className="flex items-center gap-4">
                    <div
                      className={`flex h-10 w-10 items-center justify-center rounded-full ${
                        isCritical
                          ? "bg-red-500/10"
                          : "bg-amber-500/10"
                      }`}
                    >
                      <AlertTriangle
                        className={`h-5 w-5 ${
                          isCritical ? "text-red-500" : "text-amber-500"
                        }`}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-foreground">
                        {skuLabels[sku.sku] ?? sku.sku}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {sku.doh.doh_t30 !== null
                          ? `${Math.round(sku.doh.doh_t30)} days on hand`
                          : "No DOH data"}{" "}
                        — {sku.doh.current_inventory.toLocaleString()} units
                      </p>
                    </div>
                  </div>
                  <StatusBadge status={status} doh={sku.doh.doh_t30} />
                </CardContent>
              </Card>
            )
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center py-16 text-center">
            <Bell className="h-10 w-10 text-green-500" />
            <p className="mt-3 text-lg font-medium text-foreground">
              No active alerts
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              All SKUs are above the 30-day threshold. You&apos;re in good shape.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
