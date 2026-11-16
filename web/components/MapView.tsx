"use client";

import { MapboxOverlay } from "@deck.gl/mapbox";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef, useState } from "react";

import { colorFor, type Layer } from "@/lib/layers";
import { windArrows, type WindVector } from "@/lib/wind";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BASEMAP =
  "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const HOTSPOT_ZOOM = 9;
// Di bawah zoom ini heksagon res 7 lebih kecil dari satu piksel, jadi digambar sebagai titik.
const HEX_ZOOM = 7;
// Panah angin 2 piksel per km/jam di zoom berapa pun.
const ARROW_PX_PER_KMH = 2;

type Cell = {
  h3_index: string;
  value: unknown;
  priority_score: number;
  center: [number, number];
  regency: string | null;
  province: string | null;
};
type Hotspot = {
  coordinates: [number, number];
  frp: number | null;
  acq_datetime: string;
};

async function getJson(path: string) {
  const response = await fetch(API + path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

export default function MapView({ layer }: { layer: Layer }) {
  const container = useRef<HTMLDivElement>(null);
  const overlay = useRef<MapboxOverlay>(null);
  const [map, setMap] = useState<maplibregl.Map>();
  const [cells, setCells] = useState<Cell[]>([]);
  const [day, setDay] = useState<string>();
  const [wind, setWind] = useState<WindVector[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [error, setError] = useState<string>();
  const [zoom, setZoom] = useState(0);

  useEffect(() => {
    const instance = new maplibregl.Map({
      container: container.current!,
      style: BASEMAP,
      bounds: [94.5, -11.5, 141.5, 6.5],
      fitBoundsOptions: {
        padding: { left: 270, top: 20, right: 20, bottom: 20 },
      },
      hash: true,
    });
    instance.addControl(new maplibregl.NavigationControl(), "bottom-right");
    overlay.current = new MapboxOverlay({ layers: [] });
    instance.addControl(overlay.current);
    instance.on("zoomend", () => setZoom(instance.getZoom()));
    setZoom(instance.getZoom());
    setMap(instance);
    return () => instance.remove();
  }, []);

  useEffect(() => {
    let stale = false;
    getJson(`/api/cells?layer=${layer.id}`)
      .then((body) => {
        if (stale) return;
        type Feature = {
          properties: Cell;
          geometry: { coordinates: [number, number][][] };
        };
        const parsed = body.features.map(
          ({ properties, geometry }: Feature) => {
            const ring = geometry.coordinates[0].slice(0, -1);
            const mean = (i: number) =>
              ring.reduce((sum, p) => sum + p[i], 0) / ring.length;
            return { ...properties, center: [mean(0), mean(1)] };
          },
        );
        // Prioritas tertinggi digambar terakhir supaya tidak tertutup sel lain.
        parsed.sort((a: Cell, b: Cell) => a.priority_score - b.priority_score);
        setCells(parsed);
        setDay(body.date);
        setError(undefined);
      })
      .catch((e) => !stale && setError(String(e)));
    return () => {
      stale = true;
    };
  }, [layer.id]);

  useEffect(() => {
    if (layer.id !== "wind" || !day) return;
    getJson(`/api/wind?date=${day}`)
      .then((body) => setWind(body.vectors))
      .catch((e) => setError(String(e)));
  }, [layer.id, day]);

  // Titik api mentah hanya dimuat untuk viewport saat zoom dekat, supaya payload tetap kecil.
  useEffect(() => {
    if (!map || !day) return;
    let request = 0;
    const load = () => {
      const id = ++request;
      if (map.getZoom() <= HOTSPOT_ZOOM) return setHotspots([]);
      const bbox = map.getBounds().toArray().flat().join(",");
      getJson(`/api/hotspots?date=${day}&bbox=${bbox}`)
        .then((body) => {
          if (id !== request) return;
          setHotspots(
            body.features.map(
              (f: {
                geometry: { coordinates: [number, number] };
                properties: Hotspot;
              }) => ({
                ...f.properties,
                coordinates: f.geometry.coordinates,
              }),
            ),
          );
        })
        .catch((e) => setError(String(e)));
    };
    load();
    map.on("moveend", load);
    return () => {
      map.off("moveend", load);
    };
  }, [map, day]);

  useEffect(() => {
    overlay.current?.setProps({
      layers: [
        zoom >= HEX_ZOOM
          ? new H3HexagonLayer<Cell>({
              id: "cells",
              data: cells,
              getHexagon: (d) => d.h3_index,
              getFillColor: (d) => colorFor(layer, d.value),
              updateTriggers: { getFillColor: layer.id },
              extruded: false,
              stroked: false,
              pickable: true,
            })
          : new ScatterplotLayer<Cell>({
              id: "cell-dots",
              data: cells,
              getPosition: (d) => d.center,
              getRadius: 1500,
              radiusMinPixels: 3,
              getFillColor: (d) => colorFor(layer, d.value),
              updateTriggers: { getFillColor: layer.id },
              pickable: true,
            }),
        layer.id === "wind" &&
          new LineLayer({
            id: "wind",
            data: windArrows(wind, (ARROW_PX_PER_KMH * 360) / 512 / 2 ** zoom),
            getSourcePosition: (d) => d.from,
            getTargetPosition: (d) => d.to,
            getColor: [230, 240, 255, 220],
            getWidth: 1.5,
          }),
        new ScatterplotLayer<Hotspot>({
          id: "hotspots",
          data: hotspots,
          getPosition: (d) => d.coordinates,
          getRadius: (d) => 150 + 20 * Math.sqrt(d.frp ?? 0),
          radiusMinPixels: 2,
          getFillColor: [255, 245, 160, 230],
          pickable: true,
        }),
      ],
      getTooltip: ({ object, layer: picked }) => {
        if (!object) return null;
        if (picked?.id === "hotspots")
          return `Titik api\nFRP ${object.frp ?? "-"} MW\n${object.acq_datetime}`;
        const value = object.value ?? "tidak ada data";
        const place = [object.regency, object.province]
          .filter(Boolean)
          .join(", ");
        return `${layer.label}: ${typeof value === "number" ? value.toFixed(1) : value}\n${layer.unit}\n${place}`;
      },
    });
  }, [cells, wind, hotspots, layer, zoom]);

  return (
    <div className="absolute inset-0">
      <div ref={container} className="h-full w-full" />
      {error && (
        <p
          role="alert"
          className="absolute top-3 left-1/2 -translate-x-1/2 rounded bg-red-900/90 px-3 py-1.5 text-sm text-white"
        >
          Gagal memuat data: {error}
        </p>
      )}
      {day && (
        <p className="absolute top-3 right-3 rounded bg-neutral-900/85 px-3 py-1.5 text-sm text-neutral-200">
          Data {day}
        </p>
      )}
    </div>
  );
}
