export default function ErrorState({ message }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center">
      <p className="text-sm font-medium text-red-800">Couldn't analyze that PR</p>
      <p className="mt-1 text-sm text-red-600">{message}</p>
    </div>
  );
}
