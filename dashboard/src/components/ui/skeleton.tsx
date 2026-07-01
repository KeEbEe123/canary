// Loading placeholder with a soft pulse — used while queries are in flight.
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse-soft rounded-md bg-surface-2", className)} />;
}
