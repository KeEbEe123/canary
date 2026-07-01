// Alert Rules — CRUD-lite for spike detection. List existing rules and their
// scope/condition, create new ones in a dialog, and see recent firings.
import { useState } from "react";
import { Bell, Plus, Zap } from "lucide-react";
import { PageHeader } from "@/components/Layout";
import { AlertRuleForm } from "@/components/AlertRuleForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtAgo } from "@/lib/format";
import { useAlerts } from "@/hooks/useAlerts";

export function AlertRules() {
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useAlerts();

  return (
    <>
      <PageHeader
        title="Alerts"
        subtitle="fire when failure rate spikes"
        actions={
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="h-3.5 w-3.5" /> New rule
          </Button>
        }
      />

      <div className="mx-auto max-w-4xl space-y-6 p-6">
        {isLoading && <Skeleton className="h-40 w-full" />}

        {/* Rules */}
        <div className="space-y-3">
          {data?.rules.length === 0 && (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
              <Bell className="h-8 w-8 text-muted" />
              <div>
                <p className="text-sm font-medium">No alert rules</p>
                <p className="text-xs text-muted">
                  Create a rule to get pinged when a tool or agent starts failing.
                </p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
                <Plus className="h-3.5 w-3.5" /> New rule
              </Button>
            </div>
          )}

          {data?.rules.map((rule) => (
            <Card key={rule.id} className="p-4">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{rule.name}</span>
                    <Badge variant={rule.enabled ? "success" : "muted"}>
                      {rule.enabled ? "active" : "off"}
                    </Badge>
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted">
                    {rule.condition} · over {rule.window_minutes}m
                    {rule.scope.tool && ` · tool=${rule.scope.tool}`}
                    {rule.scope.agent && ` · agent=${rule.scope.agent}`}
                  </p>
                </div>
                <Badge variant="accent">{rule.channel}</Badge>
              </div>
            </Card>
          ))}
        </div>

        {/* Recent firings */}
        {data && data.recent_firings.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-warning" /> Recent firings
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.recent_firings.map((f) => (
                <div
                  key={f.id}
                  className="flex items-center justify-between gap-3 rounded-md bg-surface-2/50 px-3 py-2 text-xs"
                >
                  <span className="min-w-0 truncate text-fg">{f.message}</span>
                  <span className="shrink-0 text-muted">{fmtAgo(f.fired_at)}</span>
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={open} onClose={() => setOpen(false)} title="New alert rule">
        <AlertRuleForm onDone={() => setOpen(false)} />
      </Dialog>
    </>
  );
}
