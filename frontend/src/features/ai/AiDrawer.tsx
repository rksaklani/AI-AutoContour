import { IconChevronRight, IconSparkles } from "@/components/icons";
import { AiChatPanel } from "@/features/ai/AiChatPanel";
import { FindingsPanel } from "@/features/findings/FindingsPanel";
import { ReportPanel } from "@/features/reports/ReportPanel";
import { useViewerStore } from "@/store/viewerStore";
import type { Finding } from "@/types";

export function AiDrawer({
  studyId,
  findings,
  enabled,
}: {
  studyId: string;
  findings: Finding[];
  enabled: boolean;
}) {
  const open = useViewerStore((s) => s.rightDrawerOpen);
  const toggle = useViewerStore((s) => s.toggleRightDrawer);

  if (!open) {
    return (
      <button
        type="button"
        onClick={toggle}
        title="Open AI panel"
        className="flex w-10 shrink-0 flex-col items-center gap-2 border-l border-surface-700 bg-surface-900 py-3 text-slate-400 hover:text-brand-300"
      >
        <IconSparkles width={18} height={18} />
        <span className="[writing-mode:vertical-rl] text-[11px] font-semibold uppercase tracking-wider">
          AI Assistant
        </span>
      </button>
    );
  }

  return (
    <div className="flex w-80 shrink-0 flex-col border-l border-surface-700 bg-surface-900">
      <div className="flex items-center justify-between border-b border-surface-700 px-3 py-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-300">
          <IconSparkles width={16} height={16} className="text-brand-400" />
          AI Assistant
        </div>
        <button
          type="button"
          onClick={toggle}
          title="Collapse panel"
          className="text-slate-400 hover:text-slate-100"
        >
          <IconChevronRight width={18} height={18} />
        </button>
      </div>
      <div className="flex flex-1 flex-col gap-2 overflow-auto p-2">
        <FindingsPanel findings={findings} />
        <AiChatPanel studyId={studyId} enabled={enabled} />
        <ReportPanel studyId={studyId} canReport={enabled} />
      </div>
    </div>
  );
}
