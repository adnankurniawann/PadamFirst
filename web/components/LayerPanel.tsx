import { GROUPS, LAYERS, type Layer } from "@/lib/layers";

export default function LayerPanel({
  active,
  onSelect,
}: {
  active: Layer;
  onSelect: (layer: Layer) => void;
}) {
  return (
    <nav
      aria-label="Layer peta"
      className="flex min-h-0 flex-col gap-3 overflow-y-auto"
    >
      {GROUPS.map((group) => (
        <section key={group}>
          <h2 className="mb-1 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
            {group}
          </h2>
          <ul className="flex flex-col gap-0.5">
            {LAYERS.filter((layer) => layer.group === group).map((layer) => (
              <li key={layer.id}>
                <button
                  type="button"
                  aria-pressed={layer.id === active.id}
                  onClick={() => onSelect(layer)}
                  className={`w-full rounded px-2 py-1 text-left text-sm ${
                    layer.id === active.id
                      ? "bg-orange-600 font-medium text-white"
                      : "text-neutral-200 hover:bg-neutral-800"
                  }`}
                >
                  {layer.label}
                </button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </nav>
  );
}
