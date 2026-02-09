"use client"

import { Card, CardContent } from "@/components/ui/card"
import { ShoppingCart } from "lucide-react"

export default function ApprovalsPage() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-col items-center py-16 text-center">
          <ShoppingCart className="h-10 w-10 text-muted-foreground" />
          <p className="mt-3 text-lg font-medium text-foreground">
            Procurement Approvals
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            No pending procurement orders. Orders will appear here when the
            agentic workflow generates purchase recommendations.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
