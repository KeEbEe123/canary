// StatCard — a single headline metric with an icon and optional sub-label.
// Used across the stats overview for total runs, success rate, cost, etc.
import * as React from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  tone?: "default" | "success" | "danger" | "accent";
}) {
  const toneClass = {
    default: "text-fg",
    success: "text-success",
    danger: "text-danger",
    accent: "text-accent",
  }[tone];

  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{label}</p>
          <p className={cn("mt-2 text-2xl font-semibold tabular-nums", toneClass)}>{value}</p>
          {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
        </div>
        <div className="rounded-md bg-surface-2 p-2">
          <Icon className={cn("h-4 w-4", toneClass)} />
        </div>
      </div>
    </Card>
  );
}
