import { cn } from "@/lib/utils"
import type { DOHStatus } from "./kpi-card"

interface StatusBadgeProps {
  status: DOHStatus
  doh?: number | null
  className?: string
}

const config: Record<DOHStatus, { label: string; className: string }> = {
  critical: {
    label: "Critical",
    className: "bg-red-500/10 text-red-500 border-red-500/20",
  },
  warning: {
    label: "Warning",
    className: "bg-amber-500/10 text-amber-500 border-amber-500/20",
  },
  healthy: {
    label: "Healthy",
    className: "bg-emerald-500/10 text-emerald-500 border-emerald-500/20",
  },
  overstocked: {
    label: "Overstocked",
    className: "bg-violet-500/10 text-violet-500 border-violet-500/20",
  },
  "no-data": {
    label: "No Data",
    className: "bg-muted text-muted-foreground border-border",
  },
}

function StatusIcon({ status }: { status: DOHStatus }) {
  const size = "h-2.5 w-2.5"

  switch (status) {
    case "critical":
      // Square
      return <span className={cn(size, "rounded-none bg-red-500")} />
    case "warning":
      // Triangle (CSS)
      return (
        <span
          className="inline-block"
          style={{
            width: 0,
            height: 0,
            borderLeft: "5px solid transparent",
            borderRight: "5px solid transparent",
            borderBottom: "8px solid #f59e0b",  /* amber-500 */
          }}
        />
      )
    case "healthy":
      // Circle
      return <span className={cn(size, "rounded-full bg-emerald-500")} />
    case "overstocked":
      // Diamond (rotated square)
      return <span className={cn("h-2 w-2 rotate-45 bg-violet-500")} />
    case "no-data":
      // Dash
      return <span className="inline-block h-0.5 w-2.5 bg-muted-foreground" />
  }
}

export function StatusBadge({ status, doh, className }: StatusBadgeProps) {
  const cfg = config[status]

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-medium",
        cfg.className,
        className
      )}
    >
      <StatusIcon status={status} />
      {cfg.label}
      {doh !== undefined && doh !== null && (
        <span className="font-data ml-0.5">{Math.round(doh)}d</span>
      )}
    </span>
  )
}
