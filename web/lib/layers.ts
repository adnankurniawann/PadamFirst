// 14 layer PRD bagian 3. id sama dengan /api/layers, warna dan satuan didefinisikan di sini.

export type RGBA = [number, number, number, number];

// stops: [nilai, warna] naik, diinterpolasi linear. step: warna pakai stop terakhir yang dilewati.
type Scale =
  | {
      kind: "stops";
      stops: [number, string][];
      step?: boolean;
      labels?: string[];
    }
  | { kind: "category"; items: [string, string, string][] };

export type Layer = {
  id: string;
  label: string;
  group: string;
  unit: string;
  scale: Scale;
};

export const GROUPS = [
  "Hasil",
  "Api",
  "Bahan bakar",
  "Cuaca",
  "Dampak",
  "Model",
];

export const LAYERS: Layer[] = [
  {
    id: "priority",
    label: "Prioritas gabungan",
    group: "Hasil",
    unit: "skor 0-100",
    scale: {
      kind: "stops",
      step: true,
      stops: [
        [0, "#2ca25f"],
        [30, "#fed976"],
        [50, "#fd8d3c"],
        [70, "#e31a1c"],
      ],
      labels: [
        "Hijau, padam sendiri",
        "Kuning, pantau",
        "Oranye, 24 jam",
        "Merah, hari ini",
      ],
    },
  },
  {
    id: "intensity",
    label: "Intensitas",
    group: "Api",
    unit: "MW per sel",
    scale: {
      kind: "stops",
      stops: [
        [0, "#ffffb2"],
        [10, "#fecc5c"],
        [50, "#fd8d3c"],
        [200, "#f03b20"],
        [500, "#bd0026"],
      ],
    },
  },
  {
    id: "detection",
    label: "Keyakinan deteksi",
    group: "Api",
    unit: "0 low, 0,5 nominal, 1 high",
    scale: {
      kind: "stops",
      stops: [
        [0, "#525252"],
        [0.5, "#a3a3a3"],
        [1, "#ffffff"],
      ],
    },
  },
  {
    id: "persistence",
    label: "Persistensi",
    group: "Api",
    unit: "hari berturut-turut",
    scale: {
      kind: "stops",
      stops: [
        [1, "#fef0d9"],
        [2, "#fdcc8a"],
        [3, "#fc8d59"],
        [5, "#e34a33"],
        [7, "#b30000"],
      ],
    },
  },
  {
    id: "growth",
    label: "Pertumbuhan",
    group: "Api",
    unit: "perubahan titik per 24 jam",
    scale: {
      kind: "stops",
      stops: [
        [-10, "#2166ac"],
        [-3, "#67a9cf"],
        [0, "#f7f7f7"],
        [3, "#ef8a62"],
        [10, "#b2182b"],
      ],
    },
  },
  {
    id: "peat",
    label: "Gambut",
    group: "Bahan bakar",
    unit: "persen area",
    scale: {
      kind: "stops",
      stops: [
        [0, "#f6e8c3"],
        [25, "#dfc27d"],
        [50, "#bf812d"],
        [75, "#8c510a"],
        [100, "#543005"],
      ],
    },
  },
  {
    id: "landcover",
    label: "Tutupan lahan",
    group: "Bahan bakar",
    unit: "kelas tutupan (ESA WorldCover)",
    scale: {
      kind: "category",
      items: [
        ["hutan", "#006400", "Hutan"],
        ["semak", "#ffbb22", "Semak"],
        ["padang_rumput", "#ffff4c", "Padang rumput"],
        ["pertanian", "#f096ff", "Pertanian"],
        ["permukiman", "#fa0000", "Permukiman"],
        ["lahan_terbuka", "#b4b4b4", "Lahan terbuka"],
        ["air", "#0064c8", "Air"],
        ["lahan_basah", "#0096a0", "Lahan basah"],
        ["mangrove", "#00cf75", "Mangrove"],
      ],
    },
  },
  {
    id: "wind",
    label: "Angin",
    group: "Cuaca",
    unit: "km/jam, panah searah tiupan",
    scale: {
      kind: "stops",
      stops: [
        [0, "#eff3ff"],
        [5, "#bdd7e7"],
        [10, "#6baed6"],
        [15, "#3182bd"],
        [25, "#08519c"],
      ],
    },
  },
  {
    id: "rain",
    label: "Curah hujan 7 hari",
    group: "Cuaca",
    unit: "mm",
    scale: {
      kind: "stops",
      stops: [
        [0, "#f0f9e8"],
        [10, "#bae4bc"],
        [30, "#7bccc4"],
        [70, "#43a2ca"],
        [150, "#0868ac"],
      ],
    },
  },
  {
    id: "drought",
    label: "Kekeringan (Drought Code)",
    group: "Cuaca",
    unit: "indeks",
    scale: {
      kind: "stops",
      stops: [
        [0, "#ffffd4"],
        [100, "#fed98e"],
        [200, "#fe9929"],
        [350, "#d95f0e"],
        [500, "#993404"],
      ],
    },
  },
  {
    id: "temperature",
    label: "Suhu maksimum",
    group: "Cuaca",
    unit: "derajat C",
    scale: {
      kind: "stops",
      stops: [
        [24, "#fee5d9"],
        [28, "#fcae91"],
        [31, "#fb6a4a"],
        [34, "#de2d26"],
        [38, "#a50f15"],
      ],
    },
  },
  {
    id: "population",
    label: "Kepadatan penduduk",
    group: "Dampak",
    unit: "jiwa per km2",
    scale: {
      kind: "stops",
      stops: [
        [0, "#f1eef6"],
        [10, "#d7b5d8"],
        [100, "#df65b0"],
        [500, "#dd1c77"],
        [2000, "#980043"],
      ],
    },
  },
  {
    id: "human",
    label: "Jarak ke jalan",
    group: "Dampak",
    unit: "km ke jalan terdekat",
    scale: {
      kind: "stops",
      stops: [
        [0, "#ffffcc"],
        [1, "#c2e699"],
        [5, "#78c679"],
        [15, "#31a354"],
        [40, "#006837"],
      ],
    },
  },
  {
    id: "confidence",
    label: "Keyakinan prediksi",
    group: "Model",
    unit: "rendah, sedang, tinggi",
    scale: {
      kind: "category",
      items: [
        ["rendah", "#54278f", "Rendah"],
        ["sedang", "#9e9ac8", "Sedang"],
        ["tinggi", "#dadaeb", "Tinggi"],
      ],
    },
  },
];

export const NO_DATA: RGBA = [140, 140, 140, 90];
const ALPHA = 210;

export function hexToRgba(hex: string): RGBA {
  const n = parseInt(hex.slice(1), 16);
  return [n >> 16, (n >> 8) & 255, n & 255, ALPHA];
}

export function colorFor(layer: Layer, value: unknown): RGBA {
  const { scale } = layer;
  if (scale.kind === "category") {
    const item = scale.items.find(([key]) => key === value);
    return item ? hexToRgba(item[1]) : NO_DATA;
  }
  if (typeof value !== "number" || !Number.isFinite(value)) return NO_DATA;
  const { stops } = scale;
  const upper = stops.findIndex(([v]) => value < v);
  if (upper === 0) return hexToRgba(stops[0][1]);
  if (upper === -1) return hexToRgba(stops[stops.length - 1][1]);
  if (scale.step) return hexToRgba(stops[upper - 1][1]);
  const [v0, c0] = stops[upper - 1];
  const [v1, c1] = stops[upper];
  const t = (value - v0) / (v1 - v0);
  const a = hexToRgba(c0);
  const b = hexToRgba(c1);
  return [0, 1, 2]
    .map((i) => Math.round(a[i] + (b[i] - a[i]) * t))
    .concat(ALPHA) as RGBA;
}
