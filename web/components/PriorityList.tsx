import { formatNumber } from "@/lib/api";
import { CLASSES } from "@/lib/layers";

export type Priority = {
  rank: number;
  h3_index: string;
  province: string | null;
  regency: string | null;
  priority_score: number;
  priority_class: string;
};

type Props = {
  summary?: Record<string, number>;
  items: Priority[];
  exportUrl: string;
  onPick: (h3: string) => void;
};

export default function PriorityList({
  summary,
  items,
  exportUrl,
  onPick,
}: Props) {
  return (
    <>
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-white">Prioritas pemadaman</h2>
        <a
          href={exportUrl}
          className="rounded bg-neutral-700 px-2 py-1 text-xs text-white hover:bg-neutral-600"
        >
          Ekspor CSV
        </a>
      </div>
      <dl className="grid grid-cols-4 gap-1 text-center">
        {Object.entries(CLASSES).map(([key, { color, label }]) => (
          <div key={key} className="rounded bg-neutral-800 py-1">
            <dt className="flex items-center justify-center gap-1 text-xs text-neutral-400">
              <span
                className="h-2 w-2 rounded-full"
                style={{ background: color }}
              />
              {label}
            </dt>
            <dd className="text-lg font-semibold text-white">
              {summary?.[key] ?? "-"}
            </dd>
          </div>
        ))}
      </dl>
      <ol className="-mx-1 flex-1 overflow-y-auto">
        {items.length === 0 && (
          <li className="px-1 py-2 text-sm text-neutral-400">
            Tidak ada sel aktif.
          </li>
        )}
        {items.map((item) => (
          <li key={item.h3_index}>
            <button
              type="button"
              onClick={() => onPick(item.h3_index)}
              className="flex w-full items-center gap-2 rounded px-1 py-1.5 text-left text-sm hover:bg-neutral-800"
            >
              <span className="w-6 text-right text-neutral-500">
                {item.rank}
              </span>
              <span
                className="h-3 w-3 shrink-0 rounded-sm"
                style={{ background: CLASSES[item.priority_class]?.color }}
                title={CLASSES[item.priority_class]?.label}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-neutral-100">
                  {item.regency ?? "-"}
                </span>
                <span className="block truncate text-xs text-neutral-400">
                  {item.province ?? "-"}
                </span>
              </span>
              <span className="font-semibold text-white tabular-nums">
                {formatNumber(item.priority_score)}
              </span>
            </button>
          </li>
        ))}
      </ol>
    </>
  );
}
