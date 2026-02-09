"use client"

import { usePathname } from "next/navigation"
import Link from "next/link"
import { Search, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"

const routeLabels: Record<string, string> = {
  "/": "Dashboard",
  "/inventory": "Inventory",
  "/forecast": "Forecasting",
  "/upload": "File Upload",
  "/review": "Email Review",
  "/approvals": "Approvals",
  "/analytics": "Analytics",
  "/analytics/velocity": "Velocity Trends",
  "/alerts": "Alerts",
  "/audit": "Audit Trail",
  "/settings": "Settings",
}

function getBreadcrumbs(pathname: string) {
  if (pathname === "/") return [{ label: "Dashboard", href: "/" }]

  const segments = pathname.split("/").filter(Boolean)
  const crumbs: { label: string; href: string }[] = [
    { label: "Dashboard", href: "/" },
  ]

  let path = ""
  for (const segment of segments) {
    path += `/${segment}`
    const label = routeLabels[path] ?? segment.charAt(0).toUpperCase() + segment.slice(1)
    crumbs.push({ label, href: path })
  }

  return crumbs
}

export function Topbar() {
  const pathname = usePathname()
  const { theme, setTheme } = useTheme()
  const breadcrumbs = getBreadcrumbs(pathname)
  const pageTitle = breadcrumbs[breadcrumbs.length - 1].label

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-background/80 px-6 backdrop-blur-sm">
      <div className="flex flex-col justify-center">
        <h1 className="font-heading text-lg font-semibold text-foreground">
          {pageTitle}
        </h1>
        {breadcrumbs.length > 1 && (
          <nav className="flex items-center gap-1 text-xs text-muted-foreground">
            {breadcrumbs.map((crumb, i) => (
              <span key={crumb.href} className="flex items-center gap-1">
                {i > 0 && <span>/</span>}
                {i < breadcrumbs.length - 1 ? (
                  <Link
                    href={crumb.href}
                    className="hover:text-foreground transition-colors"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="text-foreground">{crumb.label}</span>
                )}
              </span>
            ))}
          </nav>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" className="text-muted-foreground" disabled>
          <Search className="h-4 w-4" />
          <span className="sr-only">Search</span>
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
          <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
          <span className="sr-only">Toggle theme</span>
        </Button>
      </div>
    </header>
  )
}
