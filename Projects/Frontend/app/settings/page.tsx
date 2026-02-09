"use client"

import { useTheme } from "next-themes"
import { useQuery } from "@tanstack/react-query"
import { healthCheck } from "@/lib/api-client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Moon, Sun, Monitor, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export default function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const { data: health, isError } = useQuery({
    queryKey: ["health"],
    queryFn: healthCheck,
    staleTime: 10_000,
    refetchInterval: 30_000,
  })

  const themes = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ] as const

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      {/* Theme */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            Theme
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            {themes.map((t) => {
              const Icon = t.icon
              return (
                <Button
                  key={t.value}
                  variant={theme === t.value ? "default" : "outline"}
                  onClick={() => setTheme(t.value)}
                  className={cn(
                    "flex-1",
                    theme === t.value &&
                      "bg-gold text-primary-foreground hover:bg-gold-hover"
                  )}
                >
                  <Icon className="mr-2 h-4 w-4" />
                  {t.label}
                </Button>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* API Status */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium text-muted-foreground">
            API Connection
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            {isError ? (
              <>
                <XCircle className="h-5 w-5 text-destructive" />
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Disconnected
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Cannot reach backend API
                  </p>
                </div>
              </>
            ) : (
              <>
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Connected
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Status: {health?.status ?? "checking..."}
                  </p>
                </div>
              </>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
