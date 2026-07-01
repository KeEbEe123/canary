// ErrorGroupCard — one Sentry-style row in the error feed. Shows the exception
// type + sample message, where it happens (tool/agent), how many times, and
// when it was last seen. Clicking jumps to a sample run's full trace.
import { useNavigate } from "react-router-dom";
import { AlertTriangle, ChevronRight, Wrench, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fmtAgo, truncate } from "@/lib/format";
import type { ErrorGroup } from "@/api/client";

export function ErrorGroupCard({ group }: { group: ErrorGroup }) {
  const navigate = useNavigate();
  const goToSample = () => group.sample_run_id && navigate(`/runs/${group.sample_run_id}`);

  return (
    <Card
      onClick={goToSample}
      className="group cursor-pointer p-4 transition-colors hover:border-danger/40 hover:bg-surface-2/40"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-md bg-danger/10 p-2">
          <AlertTriangle className="h-4 w-4 text-danger" />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold text-fg">{group.error_type}</span>
            {group.tool && (
              <Badge variant="muted" className="font-mono">
                <Wrench className="h-3 w-3" /> {group.tool}
              </Badge>
            )}
            {group.agent && (
              <Badge variant="muted" className="font-mono">
                <Bot className="h-3 w-3" /> {group.agent}
              </Badge>
            )}
          </div>
          <p className="mt-1 truncate font-mono text-xs text-muted">
            {truncate(group.sample_message, 120)}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span>
              <span className="font-semibold text-danger">{group.count}</span> event
              {group.count === 1 ? "" : "s"}
            </span>
            <span>last seen {fmtAgo(group.last_seen)}</span>
            {group.affected_agents.length > 1 && (
              <span>{group.affected_agents.length} agents</span>
            )}
          </div>
        </div>

        <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
      </div>
    </Card>
  );
}
