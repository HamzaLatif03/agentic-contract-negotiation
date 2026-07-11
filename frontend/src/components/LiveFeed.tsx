import { useEffect, useRef } from "react";
import type { FeedEvent } from "../types";

interface LiveFeedProps {
  events: FeedEvent[];
  running: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  feasibility: "Feasibility",
  negotiation: "Negotiation",
  ranking: "Ranking",
  fairness: "Fairness",
  review: "Review",
  intake: "Intake",
};

function agentStyle(agent: string, stage: string): string {
  if (agent === "Lender") return "border-l-violet-500 bg-violet-50/50";
  if (agent === "Borrower") return "border-l-blue-500 bg-blue-50/50";
  if (stage === "negotiation" && agent === "system") return "border-l-slate-400 bg-slate-50";
  if (stage === "ranking") return "border-l-amber-500 bg-amber-50/50";
  if (stage === "fairness") return "border-l-teal-500 bg-teal-50/50";
  return "border-l-slate-300 bg-white";
}

export default function LiveFeed({ events, running }: LiveFeedProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="flex h-full min-h-[420px] flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-800">Live feed</h2>
        {running && (
          <span className="flex items-center gap-2 text-xs text-teal-600">
            <span className="h-2 w-2 animate-pulse rounded-full bg-teal-500" />
            Running
          </span>
        )}
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-4">
        {events.length === 0 && (
          <p className="text-sm text-slate-400">
            Agent messages will appear here as the workflow runs.
          </p>
        )}

        {events.map((event) => {
          const stageLabel = STAGE_LABELS[event.stage] ?? event.stage;
          const isSystemRound =
            event.agent === "system" && event.output.startsWith("---");

          if (isSystemRound) {
            return (
              <div
                key={event.id}
                className="py-1 text-center text-xs font-medium uppercase tracking-wider text-slate-400"
              >
                {event.output.replace(/---/g, "").trim()}
              </div>
            );
          }

          return (
            <div
              key={event.id}
              className={`rounded-lg border-l-4 px-3 py-2.5 ${agentStyle(event.agent, event.stage)}`}
            >
              <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                <span className="font-medium text-slate-600">[{stageLabel}]</span>
                <span>{event.agent}</span>
              </div>
              <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-800">
                {event.output}
              </pre>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
