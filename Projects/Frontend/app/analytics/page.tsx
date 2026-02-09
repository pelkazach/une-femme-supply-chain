"use client"

import { useMetrics } from "@/lib/hooks/use-metrics"
import { ShipDepChart } from "@/components/shared/ship-dep-chart"
import { VelocityTrends } from "@/components/shared/velocity-trends"
import { ChartSkeleton } from "@/components/shared/skeletons"

export default function AnalyticsPage() {
  const { data, isLoading } = useMetrics()

  return (
    <div className="space-y-6">
      {isLoading ? (
        <>
          <ChartSkeleton height="h-72" />
          <ChartSkeleton height="h-48" />
        </>
      ) : data && data.skus.length > 0 ? (
        <>
          <ShipDepChart skus={data.skus} />
          <VelocityTrends skus={data.skus} />
        </>
      ) : (
        <div className="py-16 text-center">
          <p className="text-lg font-medium text-foreground">No metrics data</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload distributor files or sync WineDirect to see analytics.
          </p>
        </div>
      )}
    </div>
  )
}
