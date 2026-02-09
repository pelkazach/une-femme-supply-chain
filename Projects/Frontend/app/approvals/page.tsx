"use client"

import { useState } from "react"
import { getDemoProcurementOrders, type ProcurementOrder } from "@/lib/demo-data"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import {
  ShoppingCart,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  DollarSign,
  Package,
  TrendingUp,
} from "lucide-react"

const urgencyColors: Record<string, string> = {
  critical: "border-rose-500/30 bg-rose-500/10 text-rose-500",
  high: "border-amber-500/30 bg-amber-500/10 text-amber-500",
  medium: "border-violet-500/30 bg-violet-500/10 text-violet-500",
  low: "border-border bg-surface-elevated text-muted-foreground",
}

const statusConfig: Record<string, { label: string; icon: typeof Clock; className: string }> = {
  pending_review: { label: "Pending Review", icon: Clock, className: "text-amber-500" },
  approved: { label: "Approved", icon: CheckCircle2, className: "text-emerald-500" },
  rejected: { label: "Rejected", icon: XCircle, className: "text-rose-500" },
}

export default function ApprovalsPage() {
  const [orders, setOrders] = useState<ProcurementOrder[]>(() => getDemoProcurementOrders())
  const [selectedOrder, setSelectedOrder] = useState<ProcurementOrder | null>(null)

  const pending = orders.filter((o) => o.approval_status === "pending_review")
  const approved = orders.filter((o) => o.approval_status === "approved")
  const rejected = orders.filter((o) => o.approval_status === "rejected")
  const totalPendingValue = pending.reduce((sum, o) => sum + o.order_value, 0)

  function handleApprove(id: string) {
    setOrders((prev) =>
      prev.map((o) =>
        o.id === id ? { ...o, approval_status: "approved" as const, reviewer: "You" } : o
      )
    )
    setSelectedOrder(null)
  }

  function handleReject(id: string) {
    setOrders((prev) =>
      prev.map((o) =>
        o.id === id ? { ...o, approval_status: "rejected" as const, reviewer: "You" } : o
      )
    )
    setSelectedOrder(null)
  }

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-500" />
              <p className="text-xs text-muted-foreground">Pending</p>
            </div>
            <p className="font-data mt-1 text-xl font-semibold text-foreground">
              {pending.length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              <p className="text-xs text-muted-foreground">Approved</p>
            </div>
            <p className="font-data mt-1 text-xl font-semibold text-foreground">
              {approved.length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <XCircle className="h-4 w-4 text-rose-500" />
              <p className="text-xs text-muted-foreground">Rejected</p>
            </div>
            <p className="font-data mt-1 text-xl font-semibold text-foreground">
              {rejected.length}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-gold" />
              <p className="text-xs text-muted-foreground">Pending Value</p>
            </div>
            <p className="font-data mt-1 text-xl font-semibold text-foreground">
              ${totalPendingValue.toLocaleString()}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Order list */}
      <div className="space-y-3">
        {orders.map((order) => {
          const status = statusConfig[order.approval_status]
          const StatusIcon = status.icon

          return (
            <Card
              key={order.id}
              className={cn(
                "cursor-pointer transition-colors hover:border-border-active",
                selectedOrder?.id === order.id && "border-gold",
                order.approval_status === "pending_review" &&
                  order.urgency === "critical" &&
                  "border-red-500/30"
              )}
              onClick={() => setSelectedOrder(order)}
            >
              <CardContent className="flex items-start justify-between gap-4 pt-6">
                <div className="flex items-start gap-4">
                  <div
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-full",
                      order.urgency === "critical"
                        ? "bg-red-500/10"
                        : order.urgency === "high"
                          ? "bg-amber-500/10"
                          : "bg-surface-elevated"
                    )}
                  >
                    {order.urgency === "critical" ? (
                      <AlertTriangle className="h-5 w-5 text-red-500" />
                    ) : (
                      <ShoppingCart className="h-5 w-5 text-muted-foreground" />
                    )}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">
                        {order.sku_label}
                      </p>
                      <Badge
                        variant="outline"
                        className={cn("text-xs", urgencyColors[order.urgency])}
                      >
                        {order.urgency}
                      </Badge>
                      <Badge variant="outline" className="text-xs">
                        {order.approval_level}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {order.sku} — {order.recommended_quantity.toLocaleString()} units
                      @ ${order.unit_price.toFixed(2)}/unit from {order.vendor}
                    </p>
                    <div className="mt-1 flex items-center gap-4 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Package className="h-3 w-3" />
                        {order.current_inventory.toLocaleString()} in stock
                      </span>
                      <span className="flex items-center gap-1">
                        <TrendingUp className="h-3 w-3" />
                        {order.doh_t30}d DOH
                      </span>
                      <span className="flex items-center gap-1">
                        <DollarSign className="h-3 w-3" />
                        ${order.order_value.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  <StatusIcon className={cn("h-4 w-4", status.className)} />
                  <span className={cn("text-xs font-medium", status.className)}>
                    {status.label}
                  </span>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Review panel */}
      {selectedOrder && selectedOrder.approval_status === "pending_review" && (
        <Card className="border-gold/30">
          <CardHeader>
            <CardTitle className="text-sm">
              Review Order — {selectedOrder.sku_label}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4 text-sm text-foreground">
              <p className="font-medium text-muted-foreground mb-2">Agent Reasoning</p>
              <p>{selectedOrder.reasoning}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <div>
                <p className="text-xs text-muted-foreground">Quantity</p>
                <p className="font-data font-semibold text-foreground">
                  {selectedOrder.recommended_quantity.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Unit Price</p>
                <p className="font-data font-semibold text-foreground">
                  ${selectedOrder.unit_price.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Total Value</p>
                <p className="font-data font-semibold text-foreground">
                  ${selectedOrder.order_value.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Vendor</p>
                <p className="font-data font-semibold text-foreground">
                  {selectedOrder.vendor}
                </p>
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => handleApprove(selectedOrder.id)}
                className="flex-1 bg-green-600 text-white hover:bg-green-700"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Approve Order
              </Button>
              <Button
                variant="destructive"
                onClick={() => handleReject(selectedOrder.id)}
                className="flex-1"
              >
                <XCircle className="mr-2 h-4 w-4" />
                Reject
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
