"use client"

import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { getAuditLogs } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { TableSkeleton } from "@/components/shared/skeletons"
import { AgGridReact } from "ag-grid-react"
import { AllCommunityModule, ModuleRegistry, themeQuartz } from "ag-grid-community"
import type { ColDef } from "ag-grid-community"
import type { AuditLog } from "@/lib/api-types"
import { ChevronLeft, ChevronRight } from "lucide-react"

ModuleRegistry.registerModules([AllCommunityModule])

export default function AuditPage() {
  const [page, setPage] = useState(1)
  const pageSize = 25

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page, pageSize],
    queryFn: () => getAuditLogs({ page, page_size: pageSize }),
    staleTime: 30_000,
    refetchInterval: 60_000,
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

  const columnDefs = useMemo<ColDef<AuditLog>[]>(
    () => [
      {
        field: "timestamp",
        headerName: "Time",
        sortable: true,
        valueFormatter: (p) =>
          p.value ? new Date(p.value as string).toLocaleString() : "",
        flex: 1.5,
      },
      {
        field: "agent",
        headerName: "Agent",
        sortable: true,
        filter: true,
        flex: 1,
      },
      {
        field: "action",
        headerName: "Action",
        sortable: true,
        filter: true,
        flex: 1.5,
      },
      {
        field: "sku",
        headerName: "SKU",
        sortable: true,
        filter: true,
        flex: 0.8,
      },
      {
        field: "confidence",
        headerName: "Confidence",
        sortable: true,
        valueFormatter: (p) =>
          p.value !== null && p.value !== undefined
            ? `${Math.round((p.value as number) * 100)}%`
            : "—",
        flex: 0.8,
      },
      {
        field: "reasoning",
        headerName: "Reasoning",
        flex: 2,
      },
    ],
    []
  )

  const totalPages = data?.total_pages ?? 1

  return (
    <div className="space-y-6">
      {isLoading ? (
        <TableSkeleton rows={10} />
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Audit Log ({data?.total ?? 0} entries)
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="font-data text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {data && data.items.length > 0 ? (
              <div className="h-[500px]">
                <AgGridReact<AuditLog>
                  theme={gridTheme}
                  rowData={data.items}
                  columnDefs={columnDefs}
                  defaultColDef={{
                    resizable: true,
                  }}
                />
              </div>
            ) : (
              <p className="py-12 text-center text-sm text-muted-foreground">
                No audit log entries
              </p>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
