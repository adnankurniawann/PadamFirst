import { expect, test } from "vitest";

import { fillHistory, lastDays, parseCells, query, regionOptions } from "./api";

const hex = (lon: number, lat: number) => [
  [lon - 1, lat],
  [lon + 1, lat],
  [lon, lat + 1],
  [lon, lat - 1],
  [lon - 1, lat],
];

test("parseCells menghitung centroid dan mengurutkan prioritas naik", () => {
  const cells = parseCells([
    {
      properties: {
        h3_index: "a",
        value: 1,
        priority_score: 80,
        province: "Riau",
        regency: "Siak",
      },
      geometry: { coordinates: [hex(100, 0)] },
    },
    {
      properties: {
        h3_index: "b",
        value: 2,
        priority_score: 10,
        province: null,
        regency: null,
      },
      geometry: { coordinates: [hex(110, -2)] },
    },
  ] as never);
  expect(cells.map((c) => c.h3_index)).toEqual(["b", "a"]);
  expect(cells[1].center).toEqual([100, 0]);
});

test("lastDays melewati batas bulan", () => {
  expect(lastDays("2026-12-02", 3)).toEqual([
    "2026-11-30",
    "2026-12-01",
    "2026-12-02",
  ]);
});

test("fillHistory mengisi hari kosong dengan nol", () => {
  const rows = fillHistory(
    [{ date: "2026-11-15", n_hotspots: 4, frp_sum: 9 }],
    "2026-11-15",
  );
  expect(rows).toHaveLength(7);
  expect(rows[0]).toEqual({ date: "2026-11-09", n_hotspots: 0, frp_sum: 0 });
  expect(rows[6].n_hotspots).toBe(4);
});

test("regionOptions unik, terurut, dan kabupaten mengikuti provinsi", () => {
  const cell = (province: string | null, regency: string | null) =>
    ({ province, regency }) as never;
  const options = regionOptions(
    [
      cell("Riau", "Siak"),
      cell("Jambi", "Muaro Jambi"),
      cell("Riau", "Bengkalis"),
      cell("Riau", "Siak"),
      cell(null, null),
    ],
    "Riau",
    "",
  );
  expect(options.provinces).toEqual(["Jambi", "Riau"]);
  expect(options.regencies).toEqual(["Bengkalis", "Siak"]);
  const kept = regionOptions([], "Aceh", "Aceh Besar");
  expect(kept).toEqual({ provinces: ["Aceh"], regencies: ["Aceh Besar"] });
});

test("query membuang nilai kosong", () => {
  expect(
    query({ date: "2026-11-15", province: "", regency: undefined, limit: 50 }),
  ).toBe("date=2026-11-15&limit=50");
});
