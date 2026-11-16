export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function getJson(path: string) {
  const response = await fetch(API + path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

/** Query string dari nilai yang terisi saja. */
export function query(params: Record<string, string | number | undefined>) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== "",
  );
  return new URLSearchParams(
    entries.map(([k, v]) => [k, String(v)]),
  ).toString();
}

export type Cell = {
  h3_index: string;
  value: unknown;
  priority_score: number;
  center: [number, number];
  regency: string | null;
  province: string | null;
};

type Feature = {
  properties: Omit<Cell, "center">;
  geometry: { coordinates: [number, number][][] };
};

/** Fitur GeoJSON /api/cells jadi sel dengan centroid, prioritas tertinggi di akhir supaya digambar paling atas. */
export function parseCells(features: Feature[]): Cell[] {
  return features
    .map(({ properties, geometry }) => {
      const ring = geometry.coordinates[0].slice(0, -1);
      const mean = (i: number) =>
        ring.reduce((sum, p) => sum + p[i], 0) / ring.length;
      return { ...properties, center: [mean(0), mean(1)] as [number, number] };
    })
    .sort((a, b) => a.priority_score - b.priority_score);
}

/** n tanggal ISO berurutan yang berakhir di day. */
export function lastDays(day: string, n: number): string[] {
  const end = new Date(`${day}T00:00:00Z`).getTime();
  return Array.from({ length: n }, (_, i) =>
    new Date(end - (n - 1 - i) * 86_400_000).toISOString().slice(0, 10),
  );
}

export type HistoryRow = {
  date: string;
  n_hotspots: number | null;
  frp_sum: number | null;
};

/** Riwayat 7 hari dengan hari tanpa baris diisi 0 titik, supaya grafik tidak melompati tanggal. */
export function fillHistory(history: HistoryRow[], day: string): HistoryRow[] {
  const byDate = new Map(history.map((row) => [row.date, row]));
  return lastDays(day, 7).map(
    (date) => byDate.get(date) ?? { date, n_hotspots: 0, frp_sum: 0 },
  );
}

/** Pilihan filter dari sel aktif, ditambah pilihan saat ini supaya tetap tampil di tanggal tanpa sel itu. */
export function regionOptions(
  cells: Cell[],
  province: string,
  regency: string,
) {
  const sorted = (values: (string | null)[]) =>
    [...new Set(values.filter((v): v is string => !!v))].sort();
  return {
    provinces: sorted([...cells.map((c) => c.province), province]),
    regencies: sorted([
      ...cells.filter((c) => c.province === province).map((c) => c.regency),
      regency,
    ]),
  };
}

export function formatNumber(value: unknown) {
  if (typeof value !== "number") return value == null ? "-" : String(value);
  return value.toLocaleString("id-ID", { maximumFractionDigits: 1 });
}
