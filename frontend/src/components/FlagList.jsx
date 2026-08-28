import FlagCard from "./FlagCard";

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };

export default function FlagList({ flags }) {
  const sorted = [...flags].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 3) - (SEVERITY_ORDER[b.severity] ?? 3)
  );

  return (
    <ul className="space-y-3">
      {sorted.map((flag, index) => (
        <FlagCard key={`${flag.file}-${flag.tag}-${index}`} flag={flag} />
      ))}
    </ul>
  );
}
