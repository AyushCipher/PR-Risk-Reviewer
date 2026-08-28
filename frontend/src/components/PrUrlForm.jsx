import { useState } from "react";

export default function PrUrlForm({ onSubmit, disabled }) {
  const [value, setValue] = useState("");

  function handleSubmit(event) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed) {
      onSubmit(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row">
      <input
        type="url"
        required
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="https://github.com/owner/repo/pull/123"
        className="flex-1 rounded-lg border border-slate-300 px-4 py-2.5 text-sm text-slate-900 shadow-sm focus:border-slate-500 focus:outline-none focus:ring-2 focus:ring-slate-200"
        disabled={disabled}
      />
      <button
        type="submit"
        disabled={disabled}
        className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? "Analyzing…" : "Analyze PR"}
      </button>
    </form>
  );
}
