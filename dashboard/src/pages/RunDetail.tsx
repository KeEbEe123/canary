// Run Detail — the full trace for one run: a summary strip, the thought→action
// →observation reasoning log (when present), and the span timeline.
import type { ReactNode } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Brain } from "lucide-react";
import { PageHeader } from "@/components/Layout";
import { TraceTimeline } from "@/components/TraceTimeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fmtCost, fmtDuration, fmtTime } from "@/lib/format";
import { useRun } from "@/hooks/useRuns";

export function RunDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { data, isLoading } = useRun(id);

  return (
    <>
      <PageHeader
        title="Run trace"
        subtitle={id}
        actions={
          <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </Button>
        }
      />

      <div className="mx-auto max-w-5xl space-y-4 p-6">
        {isLoading && <Skeleton className="h-64 w-full" />}

        {data && (
          <>
            {/* Summary strip */}
            <Card>
              <CardContent className="flex flex-wrap items-center gap-x-8 gap-y-3 p-5">
                <Meta label="Agent" value={<span className="font-mono">{data.run.agent}</span>} />
                <Meta
                  label="Status"
                  value={
                    data.run.status === "error" ? (
                      <Badge variant="danger">{data.run.error_type ?? "error"}</Badge>
                    ) : (
                      <Badge variant="success">ok</Badge>
                    )
                  }
                />
                <Meta label="Duration" value={fmtDuration(data.run.duration_ms)} />
                <Meta label="Spans" value={String(data.run.span_count)} />
                <Meta label="Errors" value={String(data.run.error_count)} />
                <Meta label="Cost" value={fmtCost(data.run.cost_usd)} />
                <Meta label="Started" value={fmtTime(data.run.start_time)} />
              </CardContent>
            </Card>

            {/* Reasoning log */}
            {data.thoughts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-accent" /> Reasoning
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.thoughts.map((t, i) => (
                    <div key={i} className="border-l-2 border-accent/40 pl-3 text-xs">
                      <p className="text-fg">💭 {t.thought}</p>
                      {t.action && <p className="text-sky-400">⚡ {t.action}</p>}
                      {t.observation && <p className="text-muted">👁 {t.observation}</p>}
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Timeline */}
            <Card>
              <CardHeader>
                <CardTitle>Timeline</CardTitle>
              </CardHeader>
              <CardContent>
                <TraceTimeline spans={data.spans} />
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </>
  );
}

function Meta({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
      <div className="mt-1 text-sm">{value}</div>
    </div>
  );
}
