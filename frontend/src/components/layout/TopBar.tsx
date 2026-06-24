import clsx from "clsx";

import { useAuthStore } from "@/store/authStore";
import { APP_NAME } from "@/lib/config";
import { useViewerStore, type LeftTab } from "@/store/viewerStore";

const TABS: { id: LeftTab; label: string }[] = [
  { id: "data", label: "Data" },
  { id: "annotations", label: "Annotations" },
  { id: "rendering", label: "Rendering" },
];

export function TopBar({ title, showTabs }: { title?: string; showTabs?: boolean }) {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const leftTab = useViewerStore((s) => s.leftTab);
  const setLeftTab = useViewerStore((s) => s.setLeftTab);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-surface-700 bg-surface-900 px-4">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-accent text-sm font-bold text-white">
            L
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">{APP_NAME}</div>
            <div className="text-[11px] text-slate-500">AI Medical Imaging</div>
          </div>
        </div>

        {showTabs && (
          <nav className="ml-2 flex items-center gap-1 border-l border-surface-700 pl-3">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setLeftTab(t.id)}
                className={clsx(
                  "rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-colors",
                  leftTab === t.id
                    ? "bg-surface-700 text-brand-300"
                    : "text-slate-400 hover:text-slate-200",
                )}
              >
                {t.label}
              </button>
            ))}
          </nav>
        )}

        {title && !showTabs && (
          <>
            <span className="mx-2 text-slate-600">/</span>
            <span className="text-sm text-slate-300">{title}</span>
          </>
        )}
      </div>

      <div className="flex items-center gap-3">
        {title && showTabs && (
          <span className="hidden max-w-[200px] truncate text-sm text-slate-400 md:block">
            {title}
          </span>
        )}
        {user && (
          <div className="text-right leading-tight">
            <div className="text-xs font-medium text-slate-200">
              {user.full_name || user.email}
            </div>
            <div className="text-[11px] capitalize text-slate-500">{user.role ?? "user"}</div>
          </div>
        )}
        <button className="btn-ghost" onClick={logout}>
          Sign out
        </button>
      </div>
    </header>
  );
}
