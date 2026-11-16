import type { Layer } from "@/lib/layers";

export default function Legend({ layer }: { layer: Layer }) {
  const { scale } = layer;
  return (
    <div className="rounded bg-neutral-900/90 p-3 text-xs text-neutral-200 shadow-lg">
      <p className="font-semibold">{layer.label}</p>
      <p className="mb-2 text-neutral-400">{layer.unit}</p>
      {scale.kind === "stops" && !scale.step ? (
        <>
          <div
            className="h-3 w-48 rounded-sm"
            style={{
              background: `linear-gradient(to right, ${scale.stops.map(([, c]) => c).join(", ")})`,
            }}
          />
          <div className="flex w-48 justify-between">
            {scale.stops.map(([value]) => (
              <span key={value}>{value}</span>
            ))}
          </div>
        </>
      ) : (
        <ul className="flex flex-col gap-1">
          {(scale.kind === "category"
            ? scale.items.map(([key, color, label]) => [key, color, label])
            : scale.stops.map(([value, color], i) => [
                value,
                color,
                `${value}+ ${scale.labels?.[i] ?? ""}`,
              ])
          ).map(([key, color, label]) => (
            <li key={key} className="flex items-center gap-2">
              <span
                className="h-3 w-3 rounded-sm"
                style={{ background: color }}
              />
              {label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
