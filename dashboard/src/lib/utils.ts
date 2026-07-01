// Tiny class-name helper: merge conditional classes and dedupe Tailwind
// conflicts (the same pattern shadcn/ui uses).
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
