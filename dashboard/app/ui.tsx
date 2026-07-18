// Small shared presentational helpers used across pages.
import type { JobStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: JobStatus }) {
  const styles: Record<JobStatus, string> = {
    pending: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
    running: "bg-amber-200 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
    completed: "bg-emerald-200 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200",
    failed: "bg-red-200 text-red-900 dark:bg-red-900/40 dark:text-red-200",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}

export function ScoreMeter({ score }: { score: number }) {
  // score is 0..100
  const pct = Math.max(0, Math.min(100, score));
  const hue = Math.round((pct / 100) * 130); // red→green
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
        <div
          className="h-full rounded-full"
          style={{ width: `${pct}%`, backgroundColor: `hsl(${hue} 70% 45%)` }}
        />
      </div>
      <span className="text-sm font-semibold tabular-nums">{pct}</span>
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-xl border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900 ${className}`}
    >
      {children}
    </div>
  );
}
