import { useState } from "react";
import FlagCard from "./FlagCard";

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };

export default function FlagList({ flags }) {
  const [filter, setFilter] = useState("all");

  const sorted = [...flags].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
  );

  const filtered = filter === "all" ? sorted : sorted.filter((f) => f.severity === filter);

  const counts = {
    all: flags.length,
    high: flags.filter((f) => f.severity === "high").length,
    medium: flags.filter((f) => f.severity === "medium").length,
    low: flags.filter((f) => f.severity === "low").length,
  };

  const ragCount = flags.filter((f) => f.rag_context_used).length;

  return (
    <div className="space-y-4">
      {/* Filter and stats toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-1.5 text-xs">
          <button
            onClick={() => setFilter("all")}
            className={`rounded-md px-2.5 py-1 font-medium transition ${
              filter === "all"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            All ({counts.all})
          </button>
          {counts.high > 0 && (
            <button
              onClick={() => setFilter("high")}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                filter === "high"
                  ? "bg-red-600 text-white"
                  : "bg-red-50 text-red-700 hover:bg-red-100"
              }`}
            >
              High ({counts.high})
            </button>
          )}
          {counts.medium > 0 && (
            <button
              onClick={() => setFilter("medium")}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                filter === "medium"
                  ? "bg-amber-600 text-white"
                  : "bg-amber-50 text-amber-700 hover:bg-amber-100"
              }`}
            >
              Medium ({counts.medium})
            </button>
          )}
          {counts.low > 0 && (
            <button
              onClick={() => setFilter("low")}
              className={`rounded-md px-2.5 py-1 font-medium transition ${
                filter === "low"
                  ? "bg-emerald-600 text-white"
                  : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
              }`}
            >
              Low ({counts.low})
            </button>
          )}
        </div>

        {ragCount > 0 && (
          <span className="text-xs text-purple-700 bg-purple-50 border border-purple-200 rounded px-2 py-0.5 font-medium">
            🧠 {ragCount} {ragCount === 1 ? "flag" : "flags"} enriched with codebase RAG
          </span>
        )}
      </div>

      <ul className="space-y-3">
        {filtered.map((flag, index) => (
          <FlagCard key={`${flag.file}-${flag.tag}-${index}`} flag={flag} />
        ))}
      </ul>
    </div>
  );
}
