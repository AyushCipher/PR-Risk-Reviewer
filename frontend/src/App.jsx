import { useState } from "react";
import PrUrlForm from "./components/PrUrlForm";
import LoadingState from "./components/LoadingState";
import EmptyState from "./components/EmptyState";
import ErrorState from "./components/ErrorState";
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
            <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-700">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}
