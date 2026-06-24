import { useState } from "react";

import { useAiStatus, useAskStudy } from "@/api/ai";
import { Panel, Spinner } from "@/components/ui";

type ChatMessage = { role: "user" | "assistant"; text: string };

const SUGGESTIONS = [
  "Summarize the main findings",
  "What does the lung nodule mean?",
  "Explain the segmentations",
];

export function AiChatPanel({
  studyId,
  enabled,
}: {
  studyId: string;
  enabled: boolean;
}) {
  const { data: status } = useAiStatus();
  const ask = useAskStudy(studyId);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function send(question: string) {
    const q = question.trim();
    if (!q || ask.isPending) return;
    setError(null);
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    try {
      const res = await ask.mutateAsync(q);
      setMessages((m) => [...m, { role: "assistant", text: res.answer }]);
    } catch (err: unknown) {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setError(detail ?? "AI assistant unavailable");
    }
  }

  const modeLabel = status?.sidecar_mode ?? "—";
  const reachable = status?.sidecar_reachable;

  return (
    <Panel title="AI Assistant (VILA-M3)">
      <div className="flex flex-col gap-2 p-3">
        <div className="flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wider text-slate-500">
          <span
            className={`inline-block h-1.5 w-1.5 rounded-full ${reachable ? "bg-emerald-500" : "bg-amber-500"}`}
          />
          {status?.engine ?? "ai"} · mode {modeLabel}
          {status?.vila_loaded ? " · GPU VLM" : ""}
        </div>

        {!enabled ? (
          <p className="text-xs text-slate-500">Run analysis to enable the assistant.</p>
        ) : (
          <>
            <div className="max-h-48 space-y-2 overflow-y-auto rounded-md bg-surface-950 p-2 text-xs">
              {messages.length === 0 ? (
                <p className="text-slate-500">Ask about findings, segmentations, or reports.</p>
              ) : (
                messages.map((m, i) => (
                  <div
                    key={i}
                    className={
                      m.role === "user"
                        ? "text-right text-brand-300"
                        : "whitespace-pre-wrap text-slate-300"
                    }
                  >
                    {m.text}
                  </div>
                ))
              )}
              {ask.isPending && (
                <div className="flex items-center gap-2 text-slate-500">
                  <Spinner className="h-3 w-3" /> Thinking…
                </div>
              )}
            </div>

            <div className="flex flex-wrap gap-1">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="btn-ghost !px-2 !py-0.5 text-[10px]"
                  onClick={() => send(s)}
                  disabled={ask.isPending}
                >
                  {s}
                </button>
              ))}
            </div>

            <form
              className="flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <input
                className="input flex-1 !py-1.5 text-xs"
                placeholder="Ask VILA-M3…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={ask.isPending}
              />
              <button type="submit" className="btn-primary text-xs" disabled={ask.isPending || !input.trim()}>
                Send
              </button>
            </form>
          </>
        )}
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    </Panel>
  );
}
