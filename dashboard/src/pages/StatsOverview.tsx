// Stats Overview — the at-a-glance health page: headline metrics, a 7-day
// runs-vs-errors trend, and the top failing tools/agents. Deliberately focused
// on failure signal, not vanity metrics.
import { Activity, CircleCheck, CircleX, DollarSign } from "lucide-react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/Layout";
import { StatCard } from "@/components/StatCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtCost, fmtDuration, fmtPct } from "@/lib/format";
import { useStats } from "@/hooks/useStats";
import type { NameCount } from "@/api/client";

export function StatsOverview() {
  const { data, isLoading } = useStats(7);

  if (isLoading || !data) {
    return (
      <>
        <PageHeader title="Stats" subtitle="agent health at a glance" />
        <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="Stats" subtitle="agent health at a glance" />

      <div className="space-y-6 p-6">
        {/* Headline metrics */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Total runs" value={data.total_runs.toLocaleString()} icon={Activity} />
          <StatCard
            label="Success rate"
            value={fmtPct(data.success_rate)}
            icon={CircleCheck}
            tone="success"
          />
          <StatCard
            label="Error rate"
            value={fmtPct(data.error_rate)}
            icon={CircleX}
            tone={data.error_rate > 0.1 ? "danger" : "default"}
            sub={`avg ${fmtDuration(data.avg_latency_ms)} / run`}
          />
          <StatCard
            label="Est. spend"
            value={fmtCost(data.total_cost_usd)}
            icon={DollarSign}
            tone="accent"
          />
        </div>

        {/* Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Runs vs. errors — last 7 days</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data.trend} margin={{ left: -20, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="g-runs" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(45 93% 58%)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="hsl(45 93% 58%)" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="g-errs" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(0 72% 58%)" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="hsl(0 72% 58%)" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(240 5% 18%)" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "hsl(240 5% 65%)", fontSize: 11 }}
                    tickFormatter={(d: string) => d.slice(5)}
                    stroke="hsl(240 5% 18%)"
                  />
                  <YAxis
                    tick={{ fill: "hsl(240 5% 65%)", fontSize: 11 }}
                    stroke="hsl(240 5% 18%)"
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(240 6% 8%)",
                      border: "1px solid hsl(240 5% 18%)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: "hsl(240 6% 92%)" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="runs"
                    stroke="hsl(45 93% 58%)"
                    fill="url(#g-runs)"
                    strokeWidth={2}
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    stroke="hsl(0 72% 58%)"
                    fill="url(#g-errs)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Top failing */}
        <div className="grid gap-4 lg:grid-cols-2">
          <TopFailing title="Top failing tools" rows={data.top_failing_tools} />
          <TopFailing title="Top failing agents" rows={data.top_failing_agents} />
        </div>
      </div>
    </>
  );
}

function TopFailing({ title, rows }: { title: string; rows: NameCount[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.length === 0 && <p className="text-xs text-muted">No failures. 🎉</p>}
        {rows.map((row) => (
          <div key={row.name} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate font-mono text-xs">{row.name}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full bg-danger"
                style={{ width: `${Math.min(row.error_rate * 100, 100)}%` }}
              />
            </div>
            <span className="w-24 shrink-0 text-right text-xs tabular-nums text-muted">
              {row.errors}/{row.total} · {fmtPct(row.error_rate)}
            </span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
