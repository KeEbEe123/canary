// Error Feed — the headline page. Failures grouped Sentry-style, most recent
// first. This is what "your agent broke, here's the pattern" looks like.
import { AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/Layout";
import { ErrorGroupCard } from "@/components/ErrorGroupCard";
import { Skeleton } from "@/components/ui/skeleton";
import { useErrors } from "@/hooks/useErrors";

export function ErrorFeed() {
  const { data, isLoading, isError } = useErrors();
  const totalEvents = data?.reduce((sum, g) => sum + g.count, 0) ?? 0;

  return (
    <>
      <PageHeader
        title="Errors"
        subtitle={
          data ? `${data.length} groups · ${totalEvents} events` : "grouped agent failures"
        }
      />

      <div className="mx-auto max-w-4xl space-y-3 p-6">
        {isLoading && (
          <>
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-24 w-full" />
            ))}
          </>
        )}

        {isError && (
          <p className="rounded-md border border-danger/30 bg-danger/10 p-4 text-sm text-danger">
            Couldn't reach the Canary API. Is the server running on :8732?
          </p>
        )}

        {data?.length === 0 && (
          <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-20 text-center">
            <AlertTriangle className="h-8 w-8 text-muted" />
            <div>
              <p className="text-sm font-medium">No errors yet</p>
              <p className="text-xs text-muted">
                Instrument an agent with the SDK — failures will show up here, grouped.
              </p>
            </div>
          </div>
        )}

        {data?.map((group) => (
          <div key={group.fingerprint} className="animate-fade-in">
            <ErrorGroupCard group={group} />
          </div>
        ))}
      </div>
    </>
  );
}
