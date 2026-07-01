// Runs list — every agent invocation, newest first, with status/timing/cost.
// Filterable by status; each row links to the full trace.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { fmtAgo, fmtCost, fmtDuration } from "@/lib/format";
import { useRuns } from "@/hooks/useRuns";

export function RunsList() {
  const [status, setStatus] = useState<string>("");
  const { data, isLoading } = useRuns({ status: status || undefined, limit: 200 });
  const navigate = useNavigate();

  return (
    <>
      <PageHeader
        title="Runs"
        subtitle="every agent invocation, newest first"
        actions={
          <Select
            className="w-36"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="ok">Success</option>
            <option value="error">Failed</option>
          </Select>
        }
      />

      <div className="p-6">
        {isLoading ? (
          <Skeleton className="h-96 w-full" />
        ) : (
          <div className="rounded-lg border border-border bg-surface">
            <Table>
              <THead>
                <TR>
                  <TH>Status</TH>
                  <TH>Agent</TH>
                  <TH>Task</TH>
                  <TH className="text-right">Spans</TH>
                  <TH className="text-right">Duration</TH>
                  <TH className="text-right">Cost</TH>
                  <TH className="text-right">When</TH>
                </TR>
              </THead>
              <TBody>
                {data?.map((run) => (
                  <TR
                    key={run.run_id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/runs/${run.run_id}`)}
                  >
                    <TD>
                      {run.status === "error" ? (
                        <Badge variant="danger">{run.error_type ?? "error"}</Badge>
                      ) : (
                        <Badge variant="success">ok</Badge>
                      )}
                    </TD>
                    <TD className="font-mono text-xs">{run.agent}</TD>
                    <TD className="max-w-xs truncate text-xs text-muted">
                      {typeof run.task === "string" ? run.task : JSON.stringify(run.task)}
                    </TD>
                    <TD className="text-right tabular-nums text-muted">{run.span_count}</TD>
                    <TD className="text-right tabular-nums text-muted">
                      {fmtDuration(run.duration_ms)}
                    </TD>
                    <TD className="text-right tabular-nums text-muted">{fmtCost(run.cost_usd)}</TD>
                    <TD className="text-right text-xs text-muted">{fmtAgo(run.start_time)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            {data?.length === 0 && (
              <p className="p-10 text-center text-sm text-muted">No runs yet.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
