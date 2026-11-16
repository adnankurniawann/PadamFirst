"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";

import CellDetail, { type Detail } from "@/components/CellDetail";
import LayerPanel from "@/components/LayerPanel";
import Legend from "@/components/Legend";
import PriorityList, { type Priority } from "@/components/PriorityList";
import TimeSlider from "@/components/TimeSlider";
import {
  API,
  getJson,
  parseCells,
  query,
  regionOptions,
  type Cell,
} from "@/lib/api";
import { LAYERS } from "@/lib/layers";

// MapLibre butuh window, jadi peta hanya dirender di browser.
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const SELECT =
  "w-full rounded bg-neutral-800 px-2 py-1 text-sm text-neutral-100 disabled:opacity-50";

export default function Home() {
  const [layer, setLayer] = useState(LAYERS[0]);
  const [latest, setLatest] = useState<string>();
  // Kosong berarti tanggal skor terbaru, ditentukan API.
  const [day, setDay] = useState<string>();
  const [province, setProvince] = useState("");
  const [regency, setRegency] = useState("");
  const [cells, setCells] = useState<Cell[]>([]);
  const [list, setList] = useState<{
    summary: Record<string, number>;
    items: Priority[];
  }>();
  const [selectedId, setSelectedId] = useState<string>();
  const [detail, setDetail] = useState<Detail>();
  const [flyKey, setFlyKey] = useState(0);
  const [error, setError] = useState<string>();

  useEffect(() => {
    let stale = false;
    getJson(`/api/cells?${query({ layer: layer.id, date: day })}`)
      .then((body) => {
        if (stale) return;
        setCells(parseCells(body.features));
        setLatest((current) => current ?? body.date);
        setError(undefined);
      })
      .catch((e) => !stale && setError(String(e)));
    return () => {
      stale = true;
    };
  }, [layer.id, day]);

  useEffect(() => {
    let stale = false;
    getJson(
      `/api/priorities?${query({ date: day, province, regency, limit: 50 })}`,
    )
      .then((body) => !stale && setList(body))
      .catch((e) => !stale && setError(String(e)));
    return () => {
      stale = true;
    };
  }, [day, province, regency]);

  useEffect(() => {
    if (!selectedId) return;
    let stale = false;
    getJson(`/api/cells/${selectedId}?${query({ date: day })}`)
      .then((body) => !stale && setDetail(body))
      .catch((e) => !stale && setError(String(e)));
    return () => {
      stale = true;
    };
  }, [selectedId, day]);

  const visible = useMemo(
    () =>
      cells.filter(
        (c) =>
          (!province || c.province === province) &&
          (!regency || c.regency === regency),
      ),
    [cells, province, regency],
  );
  const options = useMemo(
    () => regionOptions(cells, province, regency),
    [cells, province, regency],
  );
  const selected = cells.find((c) => c.h3_index === selectedId);
  const select = useCallback((cell: Cell) => setSelectedId(cell.h3_index), []);

  return (
    <main className="relative h-full overflow-hidden bg-neutral-950 scheme-dark">
      <MapView
        layer={layer}
        cells={visible}
        day={day ?? latest}
        selected={selected}
        flyKey={flyKey}
        onSelect={select}
      />

      <aside className="absolute z-10 top-3 bottom-3 left-3 flex w-60 flex-col gap-3 rounded bg-neutral-900/90 p-3 shadow-lg">
        <h1 className="text-lg font-bold text-white">PadamFirst</h1>
        <TimeSlider
          latest={latest}
          value={day}
          onChange={(next) => {
            setDay(next);
            // Sel terpilih belum tentu aktif di tanggal lain.
            setSelectedId(undefined);
          }}
        />
        <div className="flex flex-col gap-1.5">
          <select
            aria-label="Provinsi"
            value={province}
            onChange={(e) => {
              setProvince(e.target.value);
              setRegency("");
            }}
            className={SELECT}
          >
            <option value="">Semua provinsi</option>
            {options.provinces.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
          <select
            aria-label="Kabupaten atau kota"
            value={regency}
            disabled={!province}
            onChange={(e) => setRegency(e.target.value)}
            className={SELECT}
          >
            <option value="">Semua kabupaten/kota</option>
            {options.regencies.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </div>
        <LayerPanel active={layer} onSelect={setLayer} />
      </aside>

      <aside className="absolute z-10 top-3 right-3 bottom-3 flex w-80 flex-col gap-3 rounded bg-neutral-900/90 p-3 shadow-lg">
        {detail && detail.h3_index === selectedId ? (
          <CellDetail
            detail={detail}
            onClose={() => setSelectedId(undefined)}
          />
        ) : (
          <PriorityList
            summary={list?.summary}
            items={list?.items ?? []}
            exportUrl={`${API}/api/export.csv?${query({ date: day ?? latest, province, regency })}`}
            onPick={(h3) => {
              setSelectedId(h3);
              setFlyKey((k) => k + 1);
            }}
          />
        )}
      </aside>

      <div className="absolute bottom-3 left-66 z-10">
        <Legend layer={layer} />
      </div>

      {error && (
        <p
          role="alert"
          className="absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded bg-red-900/90 px-3 py-1.5 text-sm text-white"
        >
          Gagal memuat data: {error}
        </p>
      )}
    </main>
  );
}
