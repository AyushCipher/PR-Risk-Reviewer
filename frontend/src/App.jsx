import { useState } from "react";
import PrUrlForm from "./components/PrUrlForm";
import LoadingState from "./components/LoadingState";
import EmptyState from "./components/EmptyState";
import ErrorState from "./components/ErrorState";
import RiskScoreBadge from "./components/RiskScoreBadge";
import FlagList from "./components/FlagList";
import { analyzePr } from "./api";

export default function App() {
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleSubmit(url) {
    setStatus("loading");
    setError("");
    try {
      const data = await analyzePr(url);
      setResult(data);
      setStatus("success");
    } catch (err) {
      setError(err.message || "Something went wrong.");
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-3xl px-4 py-12">
        <header className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900">PR Risk Reviewer</h1>
          <p className="mt-1 text-sm text-slate-500">
            Paste a GitHub pull request URL to flag risky changes before you merge.
          </p>
        </header>

        <PrUrlForm onSubmit={handleSubmit} disabled={status === "loading"} />

        <div className="mt-8">
          {status === "idle" && <EmptyState />}
          {status === "loading" && <LoadingState />}
          {status === "error" && <ErrorState message={error} />}
          {status === "success" && result && (
            <div className="space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <RiskScoreBadge score={result.overall_risk_score} />
                <a
                  href={result.pr_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-slate-500 hover:text-slate-700 hover:underline"
                >
                  {result.pr_url}
                </a>
              </div>
              {result.flags.length === 0 ? (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-6 py-8 text-center text-sm text-emerald-800">
                  No risky changes detected in this pull request.
                </div>
              ) : (
                <FlagList flags={result.flags} />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
