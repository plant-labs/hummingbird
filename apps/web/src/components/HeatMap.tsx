"use client";

import { useEffect, useRef } from "react";
import maplibregl, { Map, GeoJSONSource } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoBubble } from "@/lib/types";
import { bubbleColor } from "@/lib/labels";

type Props = {
  bubbles: GeoBubble[];
  selectedGeoId?: string | null;
  onSelect: (bubble: GeoBubble) => void;
};

function toGeoJSON(bubbles: GeoBubble[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: bubbles.map((b) => ({
      type: "Feature",
      properties: {
        geo_id: b.geo_id,
        name: b.name,
        count: b.count,
        intensity: b.intensity,
        color: bubbleColor(b.dominant_verification),
        radius: Math.min(48, 14 + Math.log(b.count + 1) * 12),
      },
      geometry: {
        type: "Point",
        coordinates: [b.lng, b.lat],
      },
    })),
  };
}

export default function HeatMap({ bubbles, selectedGeoId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

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
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
          },
        ],
      },
      center: [8.1, 9.6],
      zoom: 5.2,
      attributionControl: {},
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    map.on("load", () => {
      map.addSource("bubbles", {
        type: "geojson",
        data: toGeoJSON([]),
      });

      map.addLayer({
        id: "bubbles-heat",
        type: "circle",
        source: "bubbles",
        paint: {
          "circle-radius": ["get", "radius"],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.38,
          "circle-blur": 0.55,
        },
      });

      map.addLayer({
        id: "bubbles-core",
        type: "circle",
        source: "bubbles",
        paint: {
          "circle-radius": ["*", ["get", "radius"], 0.42],
          "circle-color": ["get", "color"],
          "circle-opacity": 0.92,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#f7f4ee",
        },
      });

      map.on("mouseenter", "bubbles-core", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "bubbles-core", () => {
        map.getCanvas().style.cursor = "";
      });

      map.on("click", "bubbles-core", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const geoId = feature.properties?.geo_id as string;
        const match = (map.getSource("bubbles") as GeoJSONSource)
        // resolve from latest bubbles via event detail
        const evt = new CustomEvent<string>("hummingbird:select-bubble", { detail: geoId });
        window.dispatchEvent(evt);
      });
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const handler = (e: Event) => {
      const geoId = (e as CustomEvent<string>).detail;
      const bubble = bubbles.find((b) => b.geo_id === geoId);
      if (bubble) onSelectRef.current(bubble);
    };
    window.addEventListener("hummingbird:select-bubble", handler);
    return () => window.removeEventListener("hummingbird:select-bubble", handler);
  }, [bubbles]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) {
      const t = setTimeout(() => {
        const m = mapRef.current;
        if (m?.getSource("bubbles")) {
          (m.getSource("bubbles") as GeoJSONSource).setData(toGeoJSON(bubbles));
        }
      }, 400);
      return () => clearTimeout(t);
    }
    const source = map.getSource("bubbles") as GeoJSONSource | undefined;
    if (source) source.setData(toGeoJSON(bubbles));
  }, [bubbles]);

  useEffect(() => {
    if (!selectedGeoId || !mapRef.current) return;
    const bubble = bubbles.find((b) => b.geo_id === selectedGeoId);
    if (!bubble) return;
    mapRef.current.easeTo({
      center: [bubble.lng, bubble.lat],
      zoom: Math.max(mapRef.current.getZoom(), 6.2),
      duration: 700,
    });
  }, [selectedGeoId, bubbles]);

  return <div ref={containerRef} className="h-full w-full" />;
}
