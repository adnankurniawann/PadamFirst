import { expect, test } from "vitest";

import { colorFor, hexToRgba, LAYERS, NO_DATA } from "./layers";
import { windArrows } from "./wind";

const layer = (id: string) => LAYERS.find((l) => l.id === id)!;

test("ada 14 layer dengan id unik", () => {
  expect(new Set(LAYERS.map((l) => l.id)).size).toBe(14);
});

test("prioritas memakai kelas PRD", () => {
  const priority = layer("priority");
  expect(colorFor(priority, 29.9)).toEqual(hexToRgba("#2ca25f"));
  expect(colorFor(priority, 30)).toEqual(hexToRgba("#fed976"));
  expect(colorFor(priority, 69)).toEqual(hexToRgba("#fd8d3c"));
  expect(colorFor(priority, 100)).toEqual(hexToRgba("#e31a1c"));
});

test("skala kontinu diinterpolasi dan dijepit di ujung", () => {
  const peat = layer("peat");
  expect(colorFor(peat, -5)).toEqual(hexToRgba("#f6e8c3"));
  expect(colorFor(peat, 500)).toEqual(hexToRgba("#543005"));
  const mid = colorFor(peat, 12.5);
  const [a, b] = [hexToRgba("#f6e8c3"), hexToRgba("#dfc27d")];
  expect(mid[0]).toBe(Math.round((a[0] + b[0]) / 2));
});

test("nilai kosong dan kategori tak dikenal jadi abu-abu", () => {
  expect(colorFor(layer("peat"), null)).toEqual(NO_DATA);
  expect(colorFor(layer("landcover"), "salju_es")).toEqual(NO_DATA);
  expect(colorFor(layer("landcover"), "hutan")).toEqual(hexToRgba("#006400"));
});

test("angin dari utara menghasilkan panah ke selatan", () => {
  const [shaft, ...head] = windArrows(
    [{ lat: 0, lon: 100, wind_speed: 10, wind_dir: 0 }],
    0.008,
  );
  expect(head.length).toBe(2);
  expect(shaft.to[1] < shaft.from[1]).toBe(true);
  expect(Math.abs(shaft.to[0] - shaft.from[0]) < 1e-9).toBe(true);
  expect(Math.abs(shaft.from[1] - shaft.to[1] - 0.08) < 1e-9).toBe(true);
  expect(
    windArrows([{ lat: 0, lon: 100, wind_speed: null, wind_dir: 90 }], 0.008),
  ).toEqual([]);
});
