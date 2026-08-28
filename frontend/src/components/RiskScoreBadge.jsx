function getRiskLevel(score) {
  if (score >= 50) {
    return { label: "High risk", classes: "bg-red-50 text-red-800 border-red-300" };
  }
  if (score >= 20) {
    return { label: "Moderate risk", classes: "bg-amber-50 text-amber-800 border-amber-300" };
  }
  return { label: "Low risk", classes: "bg-emerald-50 text-emerald-800 border-emerald-300" };
}

export default function RiskScoreBadge({ score }) {
  const { label, classes } = getRiskLevel(score);

  return (
    <div className={`inline-flex items-center gap-3 rounded-xl border px-5 py-3 ${classes}`}>
      <span className="text-3xl font-bold tabular-nums">{score}</span>
      <div className="flex flex-col leading-tight">
        <span className="text-xs uppercase tracking-wide opacity-70">Risk score</span>
        <span className="text-sm font-semibold">{label}</span>
      </div>
    </div>
  );
}
