"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { getReviewQueue, getReviewQueueStats, reviewEmail } from "@/lib/api-client"
import type { EmailCategory, EmailClassification } from "@/lib/api-types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import { CheckCircle2, XCircle, Mail, Clock } from "lucide-react"

const CATEGORIES: { value: EmailCategory | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "PO", label: "Purchase Orders" },
  { value: "BOL", label: "Bills of Lading" },
  { value: "INVOICE", label: "Invoices" },
  { value: "GENERAL", label: "General" },
]

export default function ReviewPage() {
  const queryClient = useQueryClient()
  const [category, setCategory] = useState<EmailCategory | "ALL">("ALL")
  const [selectedEmail, setSelectedEmail] = useState<EmailClassification | null>(null)

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["review-stats"],
    queryFn: getReviewQueueStats,
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const { data: queue, isLoading: queueLoading } = useQuery({
    queryKey: ["review-queue", category],
    queryFn: () =>
      getReviewQueue(
        category === "ALL" ? {} : { category }
      ),
    staleTime: 30_000,
    refetchInterval: 60_000,
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, approved, corrected }: {
      id: string
      approved: boolean
      corrected?: EmailCategory
    }) =>
      reviewEmail(id, {
        reviewer: "dashboard-user",
        approved,
        corrected_category: corrected ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review-queue"] })
      queryClient.invalidateQueries({ queryKey: ["review-stats"] })
      setSelectedEmail(null)
    },
  })

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {statsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="mt-2 h-6 w-12" />
              </CardContent>
            </Card>
          ))
        ) : (
          <>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Pending Review</p>
                <p className="font-data text-xl font-semibold text-foreground">
                  {stats?.pending_review ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Reviewed Today</p>
                <p className="font-data text-xl font-semibold text-foreground">
                  {stats?.reviewed_today ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Total Reviewed</p>
                <p className="font-data text-xl font-semibold text-foreground">
                  {stats?.total_reviewed ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <p className="text-xs text-muted-foreground">Avg Confidence</p>
                <p className="font-data text-xl font-semibold text-foreground">
                  {stats?.avg_confidence !== null && stats?.avg_confidence !== undefined
                    ? `${Math.round(stats.avg_confidence * 100)}%`
                    : "—"}
                </p>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Category tabs */}
      <div className="flex gap-1 rounded-lg border border-border bg-surface p-1">
        {CATEGORIES.map((cat) => (
          <Button
            key={cat.value}
            variant={category === cat.value ? "default" : "ghost"}
            size="sm"
            onClick={() => setCategory(cat.value)}
            className={cn(
              "flex-1 text-xs",
              category === cat.value &&
                "bg-gold text-primary-foreground hover:bg-gold-hover"
            )}
          >
            {cat.label}
          </Button>
        ))}
      </div>

      {/* Email list */}
      {queueLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i}>
              <CardContent className="flex items-center gap-4 pt-6">
                <Skeleton className="h-10 w-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-64" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : queue && queue.items.length > 0 ? (
        <div className="space-y-3">
          {queue.items.map((email) => (
            <Card
              key={email.id}
              className={cn(
                "cursor-pointer transition-colors hover:border-border-active",
                selectedEmail?.id === email.id && "border-gold"
              )}
              onClick={() => setSelectedEmail(email)}
            >
              <CardContent className="flex items-start gap-4 pt-6">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-surface-elevated">
                  <Mail className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between">
                    <p className="truncate text-sm font-medium text-foreground">
                      {email.subject}
                    </p>
                    <Badge
                      variant={
                        email.confidence > 0.8
                          ? "default"
                          : email.confidence > 0.5
                            ? "secondary"
                            : "destructive"
                      }
                      className="ml-2 shrink-0"
                    >
                      {Math.round(email.confidence * 100)}%
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    From: {email.sender}
                  </p>
                  <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {new Date(email.received_at).toLocaleString()}
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {email.category}
                    </Badge>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center py-12 text-center">
            <CheckCircle2 className="h-10 w-10 text-green-500" />
            <p className="mt-3 text-sm font-medium text-foreground">
              All caught up!
            </p>
            <p className="text-xs text-muted-foreground">
              No emails pending review
            </p>
          </CardContent>
        </Card>
      )}

      {/* Review modal/panel */}
      {selectedEmail && (
        <Card className="border-gold/30">
          <CardHeader>
            <CardTitle className="text-sm">Review Email</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-muted-foreground">Subject:</span>{" "}
                <span className="text-foreground">{selectedEmail.subject}</span>
              </p>
              <p>
                <span className="text-muted-foreground">From:</span>{" "}
                <span className="text-foreground">{selectedEmail.sender}</span>
              </p>
              <p>
                <span className="text-muted-foreground">Category:</span>{" "}
                <Badge variant="outline">{selectedEmail.category}</Badge>
              </p>
              <p>
                <span className="text-muted-foreground">Reasoning:</span>{" "}
                <span className="text-foreground">
                  {selectedEmail.reasoning}
                </span>
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() =>
                  approveMutation.mutate({
                    id: selectedEmail.id,
                    approved: true,
                  })
                }
                disabled={approveMutation.isPending}
                className="flex-1 bg-green-600 text-white hover:bg-green-700"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Approve
              </Button>
              <Button
                variant="destructive"
                onClick={() =>
                  approveMutation.mutate({
                    id: selectedEmail.id,
                    approved: false,
                  })
                }
                disabled={approveMutation.isPending}
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
