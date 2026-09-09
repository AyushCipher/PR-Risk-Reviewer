import { useState } from "react";
import PrUrlForm from "./components/PrUrlForm";
import LoadingState from "./components/LoadingState";
import EmptyState from "./components/EmptyState";
import ErrorState from "./components/ErrorState";
import RiskScoreBadge from "./components/RiskScoreBadge";
import FlagList from "./components/FlagList";
import HistorySidebar from "./components/HistorySidebar";
import UserBadge from "./components/UserBadge";
import ObservabilityModal from "./components/ObservabilityModal";
import { submitPr, streamAnalysis } from "./api";

export default function App() {
  const [status, setStatus] = useState("idle"); // idle | loading | streaming | success | error
  const [flags, setFlags] = useState([]);
  const [riskScore, setRiskScore] = useState(null);
  const [prUrl, setPrUrl] = useState("");
  const [error, setError] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState(null);
  const [showTelemetry, setShowTelemetry] = useState(false);

  async function handleSubmit(url) {
    setStatus("loading");
    setFlags([]);
    setRiskScore(null);
    setError("");
    setPrUrl(url);
    setCurrentAnalysisId(null);

    let analysisId;
    try {
      analysisId = await submitPr(url);
      setCurrentAnalysisId(analysisId);
    } catch (err) {
      setError(err.message || "Failed to submit PR for analysis.");
      setStatus("error");
      return;
    }

    setStatus("streaming");

    // Open SSE stream — flags arrive one by one as Celery processes them
    streamAnalysis(analysisId, {
      onFlag: (flag) => {
        setFlags((prev) => [...prev, flag]);
      },
      onDone: (score) => {
        setRiskScore(score);
        setStatus("success");
      },
      onError: (message) => {
        setError(message);
        setStatus("error");
      },
    });
  }

  function handleLoadAnalysis(analysis) {
    // Load a past analysis from the history sidebar without re-running it
    setFlags(analysis.flags || []);
    setRiskScore(analysis.overall_risk_score ?? null);
    setPrUrl(analysis.pr_url);
    setCurrentAnalysisId(analysis.id);
    setError("");
    setStatus("success");
  }

  const isLoading = status === "loading" || status === "streaming";
  const isStreaming = status === "streaming";

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-6xl px-4 py-12">
        {/* Header */}
        <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900">PR Risk Reviewer</h1>
              <span className="rounded-md bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">
                v2.0 • RAG & Fn Calling
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-500">
              Deterministic rule engine + Gemini Function Calling & semantic codebase retrieval.
            </p>
          </div>
          <UserBadge onAuthChange={(user) => setIsLoggedIn(!!user)} />
        </header>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Main content */}
          <div className="min-w-0 flex-1">
            <PrUrlForm onSubmit={handleSubmit} disabled={isLoading} />

            <div className="mt-8">
              {status === "idle" && <EmptyState />}
              {status === "loading" && <LoadingState />}
              {status === "error" && <ErrorState message={error} />}

              {(status === "streaming" || status === "success") && (
                <div className="space-y-6">
                  {/* Analysis Header Bar */}
                  <div className="flex flex-wrap items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
                    <div className="flex items-center gap-3">
                      {riskScore !== null && <RiskScoreBadge score={riskScore} />}
                      <div className="min-w-0">
                        <span className="text-xs text-slate-400 block font-medium">Analyzing Pull Request</span>
                        <a
                          href={prUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-mono font-medium text-blue-600 hover:text-blue-800 hover:underline truncate block max-w-md"
                        >
                          {prUrl}
                        </a>
                      </div>
                    </div>

                    {/* Observability Telemetry Button */}
                    {currentAnalysisId && isLoggedIn && (
                      <button
                        onClick={() => setShowTelemetry(true)}
                        className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition shadow-xs"
                      >
                        <span>📊</span> View LLM Telemetry
                      </button>
                    )}
                  </div>

                  {/* Streaming indicator */}
                  {isStreaming && (
                    <div className="flex items-center gap-2 text-sm text-slate-600 bg-blue-50/70 border border-blue-100 rounded-lg px-4 py-2.5">
                      <span className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-blue-600" />
                      <span>Running Celery worker heuristics & RAG context retrieval…</span>
                    </div>
                  )}

                  {/* Flags — appear one by one as they stream */}
                  {flags.length > 0 ? (
                    <FlagList flags={flags} />
                  ) : (
                    !isStreaming && (
                      <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-6 py-8 text-center text-sm text-emerald-800">
                        No risky changes detected in this pull request. Clean to merge!
                      </div>
                    )
                  )}
                </div>
              )}
            </div>
          </div>

          {/* History sidebar — only shown when logged in */}
          {isLoggedIn && (
            <HistorySidebar onLoadAnalysis={handleLoadAnalysis} />
          )}
        </div>
      </div>

      {/* Telemetry / Observability Modal */}
      {showTelemetry && currentAnalysisId && (
        <ObservabilityModal
          analysisId={currentAnalysisId}
          onClose={() => setShowTelemetry(false)}
        />
      )}
    </div>
  );
}
