"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import LayerPanel from "@/components/LayerPanel";
import Legend from "@/components/Legend";
import { LAYERS } from "@/lib/layers";

// MapLibre butuh window, jadi peta hanya dirender di browser.
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

export default function Home() {
  const [layer, setLayer] = useState(LAYERS[0]);
  return (
    <main className="relative h-full overflow-hidden bg-neutral-950">
      <MapView layer={layer} />
      <aside className="absolute top-3 bottom-3 left-3 flex w-60 flex-col gap-3 rounded bg-neutral-900/90 p-3 shadow-lg">
        <h1 className="text-lg font-bold text-white">PadamFirst</h1>
        <LayerPanel active={layer} onSelect={setLayer} />
      </aside>
      <div className="absolute bottom-3 left-66">
        <Legend layer={layer} />
      </div>
    </main>
  );
}
