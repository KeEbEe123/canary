// TraceTimeline — a flame-graph-style view of a run. Each span is a row with a
// horizontal bar positioned by its start offset and sized by its duration, so
// you can see sequencing and where time (or a failure) went. Error spans are
// expandable to reveal the captured traceback and failing step.
import { useState } from "react";
import { ChevronDown, ChevronRight, Sparkles, Wrench, Zap, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { fmtDuration } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { SpanOut } from "@/api/client";

const KIND_META: Record<string, { icon: typeof Zap; color: string; bar: string }> = {
  run: { icon: Sparkles, color: "text-accent", bar: "bg-accent/70" },
  llm: { icon: Zap, color: "text-violet-400", bar: "bg-violet-500/70" },
  tool: { icon: Wrench, color: "text-sky-400", bar: "bg-sky-500/70" },
  span: { icon: ChevronRight, color: "text-muted", bar: "bg-zinc-500/70" },
};

export function TraceTimeline({ spans }: { spans: SpanOut[] }) {
  // Establish the run's absolute time window to scale every bar against.
  const starts = spans.map((s) => s.start_time);
  const ends = spans.map((s) => s.end_time ?? s.start_time);
  const t0 = Math.min(...starts);
  const t1 = Math.max(...ends);
  const total = Math.max(t1 - t0, 0.001);

  // Sort by start so the timeline reads top-to-bottom in execution order.
  const ordered = [...spans].sort((a, b) => a.start_time - b.start_time);

  return (
    <div className="flex flex-col gap-1">
      {ordered.map((span) => (
        <TimelineRow key={span.span_id} span={span} t0={t0} total={total} />
      ))}
    </div>
  );
}

function TimelineRow({ span, t0, total }: { span: SpanOut; t0: number; total: number }) {
  const [open, setOpen] = useState(false);
  const meta = KIND_META[span.kind] ?? KIND_META.span;
  const Icon = meta.icon;
  const isError = span.status === "error";
  const dur = span.duration_ms ?? 0;

  const leftPct = (((span.start_time - t0) / total) * 100).toFixed(2);
  // Guarantee a sliver of width so instantaneous spans are still visible.
  const widthPct = Math.max(((span.end_time ?? span.start_time) - span.start_time) / total * 100, 1.5).toFixed(2);

  const cost = span.attributes?.cost_usd as number | undefined;
  const tokens = span.attributes?.total_tokens as number | undefined;
  const expandable = isError || span.kind === "llm";

  return (
    <div
      className={cn(
        "rounded-md border border-transparent px-2 py-1.5 transition-colors hover:bg-surface-2/50",
        isError && "bg-danger/5",
        expandable && "cursor-pointer",
      )}
      onClick={() => expandable && setOpen((v) => !v)}
    >
      <div className="flex items-center gap-3">
        <div className="flex w-48 shrink-0 items-center gap-2">
          {expandable ? (
            open ? (
              <ChevronDown className="h-3 w-3 text-muted" />
            ) : (
              <ChevronRight className="h-3 w-3 text-muted" />
            )
          ) : (
            <span className="w-3" />
          )}
          <Icon className={cn("h-3.5 w-3.5 shrink-0", isError ? "text-danger" : meta.color)} />
          <span className="truncate font-mono text-xs text-fg" title={span.name}>
            {span.name}
          </span>
        </div>

        {/* The proportional timeline lane. */}
        <div className="relative h-5 flex-1 rounded bg-surface-2/60">
          <div
            className={cn("absolute top-0 h-5 rounded", isError ? "bg-danger/70" : meta.bar)}
            style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
          />
        </div>

        <div className="flex w-28 shrink-0 items-center justify-end gap-2">
          {isError && (
            <Badge variant="danger" className="px-1.5">
              <AlertCircle className="h-3 w-3" />
            </Badge>
          )}
          <span className="font-mono text-xs tabular-nums text-muted">{fmtDuration(dur)}</span>
        </div>
      </div>

      {/* Inline details for LLM calls and errors. */}
      {open && (
        <div className="ml-48 mt-2 space-y-2 border-l border-border pl-4 text-xs">
          {span.kind === "llm" && (
            <div className="flex flex-wrap gap-2 text-muted">
              {span.attributes?.model != null && (
                <Badge variant="muted">{String(span.attributes.model)}</Badge>
              )}
              {tokens != null && <Badge variant="muted">{tokens} tokens</Badge>}
              {cost != null && <Badge variant="accent">${cost.toFixed(4)}</Badge>}
            </div>
          )}
          {isError && span.error && (
            <div className="space-y-1">
              <p className="font-mono text-danger">
                {span.error.type}: {span.error.message}
              </p>
              <p className="text-muted">
                failed at <span className="font-mono text-fg">{span.error.failed_at}</span>
              </p>
              <pre className="max-h-48 overflow-auto rounded-md bg-bg p-3 font-mono text-[11px] leading-relaxed text-muted">
                {span.error.traceback}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
