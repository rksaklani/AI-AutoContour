import clsx from "clsx";
import type { ReactNode } from "react";

export function Spinner({ className }: { className?: string }) {
  return (
    <div
      className={clsx(
        "h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-brand-400",
        className,
      )}
    />
  );
}

export function Badge({
  children,
  tone = "default",
}: {
  children: ReactNode;
  tone?: "default" | "low" | "moderate" | "high" | "brand";
}) {
  const tones: Record<string, string> = {
    default: "bg-surface-700 text-slate-300",
    brand: "bg-brand-600/20 text-brand-400",
    low: "bg-emerald-500/15 text-emerald-400",
    moderate: "bg-amber-500/15 text-amber-400",
    high: "bg-red-500/15 text-red-400",
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export function Panel({
  title,
  actions,
  children,
  className,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("panel flex flex-col overflow-hidden", className)}>
      {title && (
        <header className="flex items-center justify-between border-b border-surface-700 px-3 py-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            {title}
          </h2>
          {actions}
        </header>
      )}
      <div className="flex-1 overflow-auto">{children}</div>
    </section>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
      <p className="text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  );
}
