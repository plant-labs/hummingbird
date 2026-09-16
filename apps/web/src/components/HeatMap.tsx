"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoBubble } from "@/lib/types";
import { bubbleColor } from "@/lib/labels";

type FocusPoint = { lat: number; lng: number; key: string };

type Props = {
  bubbles: GeoBubble[];
  selectedGeoId?: string | null;
  focusPoint?: FocusPoint | null;
  onSelect: (bubble: GeoBubble) => void;
};

/** Spread bubbles that share the same pin so stacked LGAs stay clickable. */
function withDisplayOffsets(bubbles: GeoBubble[]): GeoBubble[] {
  const groups = new Map<string, GeoBubble[]>();
  for (const b of bubbles) {
    if (!Number.isFinite(Number(b.lat)) || !Number.isFinite(Number(b.lng))) continue;
    const key = `${Number(b.lat).toFixed(4)}|${Number(b.lng).toFixed(4)}`;
    const list = groups.get(key) || [];
    list.push(b);
    groups.set(key, list);
  }
  const out: GeoBubble[] = [];
  for (const group of groups.values()) {
    if (group.length === 1) {
      out.push(group[0]);
      continue;
    }
    const radiusDeg = 0.12;
    group.forEach((b, i) => {
      const angle = (2 * Math.PI * i) / group.length - Math.PI / 2;
      out.push({
        ...b,
        lat: Number(b.lat) + radiusDeg * Math.cos(angle),
        lng: Number(b.lng) + radiusDeg * Math.sin(angle),
      });
    });
  }
  return out;
}

function bubbleSize(count: number): number {
  return Math.min(48, 14 + Math.log((count || 1) + 1) * 12);
}

function makeMarkerEl(bubble: GeoBubble, selected: boolean): HTMLButtonElement {
  const size = bubbleSize(Number(bubble.count) || 1);
  const color = bubbleColor(bubble.dominant_outcome);
  const el = document.createElement("button");
  el.type = "button";
  el.title = `${bubble.name} (${bubble.count})`;
  el.setAttribute("aria-label", `Open incidents in ${bubble.name}`);
  el.dataset.geoId = bubble.geo_id;
  el.style.cssText = [
    "border:0",
    "padding:0",
    "cursor:pointer",
    "background:transparent",
    "display:grid",
    "place-items:center",
  ].join(";");

  const glow = document.createElement("span");
  glow.style.cssText = [
    `width:${size}px`,
    `height:${size}px`,
    "border-radius:999px",
    `background:${color}`,
    "opacity:0.35",
    "filter:blur(2px)",
    "grid-area:1/1",
  ].join(";");

  const core = document.createElement("span");
  const coreSize = Math.max(10, size * 0.42);
  core.style.cssText = [
    `width:${coreSize}px`,
    `height:${coreSize}px`,
    "border-radius:999px",
    `background:${color}`,
    "opacity:0.95",
    "grid-area:1/1",
    `box-shadow:0 0 0 ${selected ? 3 : 2}px ${selected ? "#1b2a22" : "#f7f4ee"}`,
  ].join(";");

  el.append(glow, core);
  return el;
}

export default function HeatMap({ bubbles, selectedGeoId, focusPoint, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const bubblesRef = useRef(bubbles);
  const onSelectRef = useRef(onSelect);
  const selectedRef = useRef(selectedGeoId);
  bubblesRef.current = bubbles;
  onSelectRef.current = onSelect;
  selectedRef.current = selectedGeoId;

  const syncMarkers = (map: maplibregl.Map, data: GeoBubble[]) => {
    try {
      let container: HTMLElement | null = null;
      try {
        container = map.getContainer();
      } catch {
        return;
      }
      if (!container || !document.contains(container)) return;

      for (const marker of markersRef.current) marker.remove();
      markersRef.current = [];

      const placed = withDisplayOffsets(data);
      for (const bubble of placed) {
        const el = makeMarkerEl(bubble, selectedRef.current === bubble.geo_id);
        el.addEventListener("click", (e) => {
          e.stopPropagation();
          window.dispatchEvent(
            new CustomEvent<string>("hummingbird:select-bubble", { detail: bubble.geo_id }),
          );
        });
        const marker = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([Number(bubble.lng), Number(bubble.lat)])
          .addTo(map);
        markersRef.current.push(marker);
      }
    } catch (err) {
      console.error("[HeatMap] syncMarkers failed", err);
    }
  };

  useEffect(() => {
    if (!containerRef.current) return;

    if (mapRef.current) {
      let alive = false;
      try {
        const c = mapRef.current.getContainer();
        alive = Boolean(c && document.contains(c));
      } catch {
        alive = false;
      }
      if (!alive) {
        try {
          mapRef.current.remove();
        } catch {
          /* ignore */
        }
        mapRef.current = null;
      }
    }
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [8.1, 9.6],
      zoom: 5.2,
      attributionControl: {},
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;

    syncMarkers(map, bubblesRef.current);
    map.on("load", () => syncMarkers(map, bubblesRef.current));
    map.on("click", () => {
      window.dispatchEvent(new CustomEvent("hummingbird:dismiss-panel"));
    });

    return () => {
      for (const marker of markersRef.current) marker.remove();
      markersRef.current = [];
      map.remove();
      if (mapRef.current === map) mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const handler = (e: Event) => {
      const geoId = (e as CustomEvent<string>).detail;
      const bubble = bubblesRef.current.find((b) => b.geo_id === geoId);
      if (bubble) onSelectRef.current(bubble);
    };
    window.addEventListener("hummingbird:select-bubble", handler);
    return () => window.removeEventListener("hummingbird:select-bubble", handler);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const trySync = () => {
      if (cancelled) return;
      const map = mapRef.current;
      if (!map) return;
      syncMarkers(map, bubblesRef.current);
    };

    trySync();
    const map = mapRef.current;
    if (map && !map.loaded()) map.once("load", trySync);
    const t0 = window.setTimeout(trySync, 0);
    const t1 = window.setTimeout(trySync, 300);

    return () => {
      cancelled = true;
      mapRef.current?.off("load", trySync);
      window.clearTimeout(t0);
      window.clearTimeout(t1);
    };
  }, [bubbles, selectedGeoId]);

  useEffect(() => {
    if (!selectedGeoId || !mapRef.current) return;
    const bubble = bubbles.find((b) => b.geo_id === selectedGeoId);
    if (!bubble || !Number.isFinite(Number(bubble.lat)) || !Number.isFinite(Number(bubble.lng))) {
      return;
    }
    mapRef.current.easeTo({
      center: [Number(bubble.lng), Number(bubble.lat)],
      zoom: Math.max(mapRef.current.getZoom(), 6.2),
      duration: 700,
    });
  }, [selectedGeoId, bubbles]);

  useEffect(() => {
    if (!focusPoint || !mapRef.current) return;
    if (!Number.isFinite(focusPoint.lat) || !Number.isFinite(focusPoint.lng)) return;
    mapRef.current.easeTo({
      center: [focusPoint.lng, focusPoint.lat],
      zoom: Math.max(mapRef.current.getZoom(), 6.5),
      duration: 700,
    });
  }, [focusPoint]);

  return (
    <div
      ref={containerRef}
      className="h-full w-full"
      data-bubble-count={bubbles.length}
    />
  );
}
