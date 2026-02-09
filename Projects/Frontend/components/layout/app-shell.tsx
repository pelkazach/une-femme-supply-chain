"use client"

import { Sidebar } from "./sidebar"
import { Topbar } from "./topbar"
import { useSidebarStore } from "@/lib/store"
import { cn } from "@/lib/utils"

export function AppShell({ children }: { children: React.ReactNode }) {
  const { collapsed, toggle } = useSidebarStore()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} onToggle={toggle} />
      <div
        className={cn(
          "transition-[margin-left] duration-200",
          collapsed ? "ml-[72px]" : "ml-[280px]"
        )}
      >
        <Topbar />
        <main className="p-6">{children}</main>
      </div>
    </div>
  )
}
