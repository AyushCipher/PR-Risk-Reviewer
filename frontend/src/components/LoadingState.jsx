export default function LoadingState() {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white py-16 text-slate-500">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
      <p className="text-sm">Analyzing pull request…</p>
    </div>
  );
}
