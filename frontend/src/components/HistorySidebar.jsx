import { useEffect, useState } from "react";
import { getHistory, getAnalysis } from "../api";

const SCORE_COLOR = (score) => {
  if (score >= 50) return "text-red-600 bg-red-50 border-red-200";
  if (score >= 20) return "text-amber-600 bg-amber-50 border-amber-200";
  return "text-emerald-600 bg-emerald-50 border-emerald-200";
};

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function prShortLabel(url) {
  // Extract "owner/repo#123" from the full GitHub URL
  const m = url.match(/github\.com\/([^/]+\/[^/]+)\/pull\/(\d+)/);
  return m ? `${m[1]}#${m[2]}` : url;
}

export default function HistorySidebar({ onLoadAnalysis }) {
  const [history, setHistory] = useState(null); // null = not loaded
  const [open, setOpen] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getHistory().then(setHistory);
  }, []);

  async function handleSelect(analysisId) {
    setLoading(true);
    try {
      const data = await getAnalysis(analysisId);
      if (data) onLoadAnalysis(data);
    } finally {
      setLoading(false);
    }
  }

  // Not logged in — history not available
  if (history === null) return null;

  return (
    <aside className="w-72 shrink-0">
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          <span>Recent analyses</span>
          <span className="text-slate-400">{open ? "▲" : "▼"}</span>
        </button>

        {open && (
          <ul className="divide-y divide-slate-100 max-h-[60vh] overflow-y-auto">
            {history.length === 0 && (
              <li className="px-4 py-6 text-center text-xs text-slate-400">
                No analyses yet. Run your first PR review!
              </li>
            )}
            {history.map((row) => (
              <li key={row.id}>
                <button
                  disabled={loading}
                  onClick={() => handleSelect(row.id)}
                  className="w-full px-4 py-3 text-left hover:bg-slate-50 disabled:opacity-50"
                >
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <span className="font-mono text-xs text-slate-700 truncate">
                      {prShortLabel(row.pr_url)}
                    </span>
                    {row.overall_risk_score != null && (
                      <span
                        className={`shrink-0 rounded border px-1.5 py-0.5 text-xs font-bold ${SCORE_COLOR(row.overall_risk_score)}`}
                      >
                        {row.overall_risk_score}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-slate-400">{formatDate(row.created_at)}</span>
                    <span
                      className={`text-xs font-medium ${
                        row.status === "done"
                          ? "text-emerald-600"
                          : row.status === "error"
                          ? "text-red-500"
                          : "text-amber-500"
                      }`}
                    >
                      {row.status}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
