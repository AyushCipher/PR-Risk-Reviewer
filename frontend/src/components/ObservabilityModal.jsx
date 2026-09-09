import { useEffect, useState } from "react";
import { getTraces } from "../api";

export default function ObservabilityModal({ analysisId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTraces(analysisId).then((res) => {
      setData(res);
      setLoading(false);
    });
  }, [analysisId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-xs">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <span>📊</span> LLM Observability & Traces
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Production telemetry for Gemini Function Calling & RAG pipeline
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto py-4 space-y-5">
          {loading && (
            <div className="py-12 text-center text-sm text-slate-400 animate-pulse">
              Loading LLM telemetry traces...
            </div>
          )}

          {!loading && !data && (
            <div className="py-8 text-center text-sm text-slate-500">
              No traces found for this analysis (traces require user login or were recorded before telemetry).
            </div>
          )}

          {!loading && data && (
            <>
              {/* Summary Stats Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3 text-center">
                  <span className="text-xs text-slate-500 block">Total Flags</span>
                  <span className="text-lg font-bold text-slate-900">{data.summary.total_flags}</span>
                </div>
                <div className="rounded-xl border border-purple-100 bg-purple-50 p-3 text-center">
                  <span className="text-xs text-purple-600 block">RAG Enhanced</span>
                  <span className="text-lg font-bold text-purple-900">{data.summary.rag_context_used}</span>
                </div>
                <div className="rounded-xl border border-emerald-100 bg-emerald-50 p-3 text-center">
                  <span className="text-xs text-emerald-600 block">Avg Latency</span>
                  <span className="text-lg font-bold text-emerald-900">{data.summary.avg_latency_ms} ms</span>
                </div>
                <div className="rounded-xl border border-blue-100 bg-blue-50 p-3 text-center">
                  <span className="text-xs text-blue-600 block">Fallback Rate</span>
                  <span className="text-lg font-bold text-blue-900">
                    {data.summary.total_flags > 0
                      ? `${Math.round((data.summary.fallback_used / data.summary.total_flags) * 100)}%`
                      : "0%"}
                  </span>
                </div>
              </div>

              {/* Individual Traces Table */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Per-Flag Execution Traces
                </h3>
                <div className="rounded-xl border border-slate-200 overflow-hidden text-xs">
                  <table className="w-full text-left">
                    <thead className="bg-slate-50 text-slate-500 border-b border-slate-200">
                      <tr>
                        <th className="py-2.5 px-3">File / Flag</th>
                        <th className="py-2.5 px-3">Model</th>
                        <th className="py-2.5 px-3">RAG</th>
                        <th className="py-2.5 px-3">Latency</th>
                        <th className="py-2.5 px-3">Result</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700 font-mono">
                      {data.traces.map((trace) => (
                        <tr key={trace.id} className="hover:bg-slate-50/70">
                          <td className="py-2 px-3 truncate max-w-[160px]" title={trace.flag_file}>
                            <span className="text-slate-900 font-medium block truncate">{trace.flag_file.split('/').pop()}</span>
                            <span className="text-[10px] text-slate-400 font-sans">{trace.flag_tag}</span>
                          </td>
                          <td className="py-2 px-3 text-[11px] text-slate-600">{trace.model_name}</td>
                          <td className="py-2 px-3 font-sans">
                            {trace.rag_context_used ? (
                              <span className="text-purple-700 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded text-[10px] font-semibold">
                                Yes
                              </span>
                            ) : (
                              <span className="text-slate-400 text-[10px]">No</span>
                            )}
                          </td>
                          <td className="py-2 px-3">{trace.latency_ms}ms</td>
                          <td className="py-2 px-3 font-sans">
                            {trace.fallback_used ? (
                              <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded text-[10px]">Fallback</span>
                            ) : (
                              <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded text-[10px] font-medium">Function Call</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="pt-3 border-t border-slate-100 flex justify-end">
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition"
          >
            Close Telemetry
          </button>
        </div>
      </div>
    </div>
  );
}
