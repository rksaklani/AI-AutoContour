import { useMemo, useState } from "react";

import { useInstanceTags } from "@/api/studies";
import { Spinner } from "@/components/ui";
import type { Study } from "@/types";

/** Collapsible DICOM tag browser for the instances of a study. */
export function TagBrowser({ study }: { study: Study }) {
  const instances = useMemo(
    () =>
      study.series.flatMap((s) =>
        s.instances.map((i) => ({
          id: i.id,
          label: `${s.description || s.modality || "Series"} · #${i.instance_number ?? "?"}`,
        })),
      ),
    [study],
  );

  const [open, setOpen] = useState(false);
  const [instanceId, setInstanceId] = useState<string | undefined>(instances[0]?.id);
  const [filter, setFilter] = useState("");

  const { data: tags = [], isLoading } = useInstanceTags(open ? study.id : undefined, instanceId);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return tags;
    return tags.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.tag.toLowerCase().includes(q) ||
        t.value.toLowerCase().includes(q),
    );
  }, [tags, filter]);

  return (
    <div className="panel p-3">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-400"
      >
        <span>DICOM Tags</span>
        <span className="text-slate-500">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {instances.length === 0 ? (
            <p className="text-xs text-slate-500">No instances uploaded.</p>
          ) : (
            <>
              {instances.length > 1 && (
                <select
                  className="input text-xs"
                  value={instanceId}
                  onChange={(e) => setInstanceId(e.target.value)}
                >
                  {instances.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.label}
                    </option>
                  ))}
                </select>
              )}
              <input
                className="input text-xs"
                placeholder="Filter tags…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              {isLoading ? (
                <div className="flex justify-center py-3">
                  <Spinner />
                </div>
              ) : (
                <ul className="max-h-72 space-y-1 overflow-auto">
                  {filtered.map((t, idx) => (
                    <li key={`${t.tag}-${idx}`} className="rounded bg-surface-800 px-2 py-1 text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate font-medium text-slate-300" title={t.name}>
                          {t.name}
                        </span>
                        <span className="shrink-0 font-mono text-[10px] text-slate-500">{t.tag}</span>
                      </div>
                      <div className="truncate text-slate-400" title={t.value}>
                        {t.value || "—"}
                      </div>
                    </li>
                  ))}
                  {filtered.length === 0 && (
                    <li className="text-xs text-slate-500">No matching tags.</li>
                  )}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
