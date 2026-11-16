import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fillHistory, formatNumber, type HistoryRow } from "@/lib/api";
import { CLASSES, LAYERS } from "@/lib/layers";

export type Detail = Record<string, unknown> & {
  h3_index: string;
  date: string;
  lat: number;
  lon: number;
  priority_score: number;
  priority_class: string;
  history: HistoryRow[];
};

const COMPONENTS = [
  ["p_spread", "Peluang menyebar (P)"],
  ["impact_score", "Dampak (D)"],
  ["fire_score", "Kondisi api (A)"],
];

export default function CellDetail({
  detail,
  onClose,
}: {
  detail: Detail;
  onClose: () => void;
}) {
  const cls = CLASSES[detail.priority_class];
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto text-sm">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-semibold text-white">
            {String(detail.regency ?? "-")}
          </h2>
          <p className="text-xs text-neutral-400">
            {String(detail.province ?? "-")}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded bg-neutral-700 px-2 py-1 text-xs text-white hover:bg-neutral-600"
        >
          Kembali ke daftar
        </button>
      </div>

      <div className="flex items-center gap-3 rounded bg-neutral-800 p-2">
        <span className="text-3xl font-bold text-white tabular-nums">
          {formatNumber(detail.priority_score)}
        </span>
        <span>
          <span className="flex items-center gap-1 text-neutral-100">
            <span
              className="h-3 w-3 rounded-sm"
              style={{ background: cls?.color }}
            />
            {cls?.label ?? detail.priority_class}
          </span>
          <span className="text-xs text-neutral-400">
            Keyakinan prediksi {String(detail.confidence_level ?? "-")}
          </span>
        </span>
      </div>

      <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
        <dt className="text-neutral-400">Centroid</dt>
        <dd className="text-right text-neutral-100 tabular-nums">
          {detail.lat.toFixed(4)}, {detail.lon.toFixed(4)}
        </dd>
        <dt className="text-neutral-400">Titik api hari ini</dt>
        <dd className="text-right text-neutral-100">
          {formatNumber(detail.n_hotspots)}
        </dd>
        {COMPONENTS.map(([key, label]) => (
          <div key={key} className="contents">
            <dt className="text-neutral-400">{label}</dt>
            <dd className="text-right text-neutral-100">
              {formatNumber(detail[key])}
            </dd>
          </div>
        ))}
      </dl>

      <section>
        <h3 className="mb-1 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
          Titik api 7 hari
        </h3>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={fillHistory(detail.history, detail.date)}>
              <XAxis
                dataKey="date"
                tickFormatter={(d: string) => d.slice(8)}
                stroke="#a3a3a3"
                fontSize={11}
              />
              <YAxis
                allowDecimals={false}
                width={28}
                stroke="#a3a3a3"
                fontSize={11}
              />
              <Tooltip
                contentStyle={{ background: "#171717", border: "none" }}
                labelStyle={{ color: "#e5e5e5" }}
                cursor={{ fill: "#ffffff14" }}
              />
              <Bar dataKey="n_hotspots" name="Titik api" fill="#fd8d3c" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section>
        <h3 className="mb-1 text-xs font-semibold tracking-wide text-neutral-400 uppercase">
          Nilai faktor
        </h3>
        <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
          {LAYERS.filter((layer) => layer.id !== "priority").map((layer) => (
            <div key={layer.id} className="contents">
              <dt className="text-neutral-400">{layer.label}</dt>
              <dd className="text-right text-neutral-100" title={layer.unit}>
                {formatNumber(detail[layer.column])}
              </dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
