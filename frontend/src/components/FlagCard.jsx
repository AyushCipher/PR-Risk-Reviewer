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
    <li className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
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
        </div>
        <span className="shrink-0 text-xs font-medium text-slate-500">
          {TAG_LABELS[flag.tag] || flag.tag}
        </span>
      </button>
      {expanded && (
        <div className="space-y-3 border-t border-slate-100 px-4 py-3">
          <p className="text-sm text-slate-700">{flag.explanation}</p>
          <p className="text-xs text-slate-500">
            <span className="font-semibold">Matched reason: </span>
            {flag.matched_reason}
          </p>
          <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">
            <code>{flag.hunk_excerpt}</code>
          </pre>
        </div>
      )}
    </li>
  );
}
