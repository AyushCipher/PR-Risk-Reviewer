import { useState } from "react";

const SEVERITY_STYLES = {
  high: "border-red-300 bg-red-50 text-red-800",
  medium: "border-amber-300 bg-amber-50 text-amber-800",
  low: "border-emerald-300 bg-emerald-50 text-emerald-800",
};

const TAG_LABELS = {
  auth_change: "Auth change",
  migration: "DB migration",
  config_change: "Config change",
  hardcoded_secret: "Hardcoded secret",
  missing_test: "Missing test",
};

export default function FlagCard({ flag }) {
  const [expanded, setExpanded] = useState(false);
  const severityClasses = SEVERITY_STYLES[flag.severity] || SEVERITY_STYLES.medium;

  return (
    <li className="rounded-lg border border-slate-200 bg-white shadow-sm transition hover:border-slate-300">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
        aria-expanded={expanded}
      >
        <div className="flex min-w-0 flex-1 items-center gap-3">
          <span
            className={`shrink-0 rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide ${severityClasses}`}
          >
            {flag.severity}
          </span>
          <span className="truncate font-mono text-sm text-slate-700">{flag.file}</span>
          {flag.rag_context_used && (
            <span
              title="Semantically retrieved surrounding codebase context was provided to Gemini"
              className="hidden sm:inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-medium text-purple-700 border border-purple-200"
            >
              🧠 RAG Context
            </span>
          )}
        </div>
        <span className="shrink-0 text-xs font-medium text-slate-500">
          {TAG_LABELS[flag.tag] || flag.tag}
        </span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3 bg-slate-50/50">
          {/* LLM Explanation */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">AI Risk Assessment</span>
              {flag.rag_context_used && (
                <span className="sm:hidden inline-flex items-center gap-1 rounded-md bg-purple-50 px-2 py-0.5 text-[10px] font-medium text-purple-700 border border-purple-200">
                  🧠 RAG Enhanced
                </span>
              )}
            </div>
            <p className="text-sm text-slate-800 leading-relaxed">{flag.explanation}</p>
          </div>

          {/* Suggested Fix — powered by Function Calling */}
          {flag.suggested_fix && (
            <div className="flex items-start gap-2.5 rounded-lg border border-blue-200 bg-blue-50/80 px-3.5 py-2.5 shadow-xs">
              <span className="mt-0.5 shrink-0 text-base">💡</span>
              <div>
                <p className="text-xs font-semibold text-blue-900">Suggested remediation</p>
                <p className="text-xs text-blue-800 mt-0.5 leading-normal">{flag.suggested_fix}</p>
              </div>
            </div>
          )}

          {/* Matched reason */}
          <p className="text-xs text-slate-500">
            <span className="font-semibold text-slate-600">Deterministic rule: </span>
            {flag.matched_reason}
          </p>

          {/* Diff excerpt */}
          <div>
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">Diff Excerpt</span>
            <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100 font-mono">
              <code>{flag.hunk_excerpt}</code>
            </pre>
          </div>
        </div>
      )}
    </li>
  );
}
