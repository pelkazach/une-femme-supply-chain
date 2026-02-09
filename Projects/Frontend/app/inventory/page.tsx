"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { getInventorySellable } from "@/lib/api-client"
import { useMetrics } from "@/lib/hooks/use-metrics"
import { getDOHStatus } from "@/components/shared/kpi-card"
import { StatusBadge } from "@/components/shared/status-badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { KpiCardSkeleton } from "@/components/shared/skeletons"
import { unitsToCases } from "@/components/shared/kpi-card"
import { Package, ArrowRight } from "lucide-react"

const skuLabels: Record<string, string> = {
  UFBub250: "Sparkling Brut",
  UFRos250: "Sparkling Rosé",
  UFRed250: "Red Blend",
  UFCha250: "Chardonnay",
}

const skuDescriptions: Record<string, string> = {
  UFBub250: "250ml Sparkling Brut",
  UFRos250: "250ml Sparkling Rosé",
  UFRed250: "250ml Red Blend",
  UFCha250: "250ml Chardonnay",
}

export default function InventoryPage() {
  const { data: inventoryData, isLoading: invLoading } = useQuery({
    queryKey: ["inventory-sellable"],
    queryFn: getInventorySellable,
    staleTime: 15_000,
    refetchInterval: 30_000,
  })

  const { data: metricsData, isLoading: metricsLoading } = useMetrics()

  const isLoading = invLoading || metricsLoading

  // Group inventory by SKU (sum across warehouses)
  const skuTotals = new Map<string, number>()
  if (inventoryData) {
    for (const item of inventoryData.items) {
      skuTotals.set(item.sku, (skuTotals.get(item.sku) ?? 0) + item.quantity)
    }
  }

  // Build metrics lookup
  const metricsMap = new Map(metricsData?.skus.map((s) => [s.sku, s]))

  const skus = Array.from(new Set([
    ...skuTotals.keys(),
    ...(metricsData?.skus.map((s) => s.sku) ?? []),
  ]))

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <KpiCardSkeleton key={i} />
            ))
          : skus.map((sku) => {
              const total = skuTotals.get(sku) ?? 0
              const metrics = metricsMap.get(sku)
              const doh = metrics?.doh.doh_t30 ?? null
              const status = getDOHStatus(doh)

              return (
                <Link key={sku} href={`/inventory/${sku}`}>
                  <Card className="transition-colors hover:border-border-active">
                    <CardHeader className="flex flex-row items-center justify-between pb-2">
                      <div className="flex items-center gap-2">
                        <Package className="h-4 w-4 text-gold" />
                        <CardTitle className="text-sm font-medium">
                          {skuLabels[sku] ?? sku}
                        </CardTitle>
                      </div>
                      <StatusBadge status={status} doh={doh} />
                    </CardHeader>
                    <CardContent>
                      <p className="font-data text-2xl font-semibold text-foreground">
                        {total.toLocaleString()}
                        <span className="ml-1.5 text-sm font-medium text-muted-foreground">
                          ({unitsToCases(total).toLocaleString()} cs)
                        </span>
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {skuDescriptions[sku] ?? sku}
                      </p>
                      <div className="mt-3 flex items-center gap-1 text-xs text-muted-foreground">
                        <span>View details</span>
                        <ArrowRight className="h-3 w-3" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              )
            })}
      </div>

      {!isLoading && skus.length === 0 && (
        <div className="py-16 text-center">
          <Package className="mx-auto h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-lg font-medium text-foreground">
            No inventory data
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload distributor files or sync WineDirect to see inventory.
          </p>
        </div>
      )}
    </div>
  )
}
