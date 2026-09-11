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
    features: bubbles
      .filter((b) => Number.isFinite(Number(b.lat)) && Number.isFinite(Number(b.lng)))
      .map((b) => ({
        type: "Feature",
        properties: {
          geo_id: b.geo_id,
          name: b.name,
          count: b.count,
          intensity: b.intensity,
          color: bubbleColor(b.dominant_outcome),
          radius: Math.min(48, 14 + Math.log(b.count + 1) * 12),
        },
        geometry: {
          type: "Point",
          coordinates: [Number(b.lng), Number(b.lat)],
        },
      })),
  };
}

export default function HeatMap({ bubbles, selectedGeoId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const bubblesRef = useRef(bubbles);
  const onSelectRef = useRef(onSelect);
  bubblesRef.current = bubbles;
  onSelectRef.current = onSelect;

  const applyBubbles = (map: Map, data: GeoBubble[]) => {
    const source = map.getSource("bubbles") as GeoJSONSource | undefined;
    if (source) source.setData(toGeoJSON(data));
  };

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
        data: toGeoJSON(bubblesRef.current),
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
        window.dispatchEvent(
          new CustomEvent<string>("hummingbird:select-bubble", { detail: geoId }),
        );
      });

      map.on("click", (e) => {
        const hits = map.queryRenderedFeatures(e.point, { layers: ["bubbles-core"] });
        if (hits.length > 0) return;
        window.dispatchEvent(new CustomEvent("hummingbird:dismiss-panel"));
      });

      applyBubbles(map, bubblesRef.current);
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
      const bubble = bubblesRef.current.find((b) => b.geo_id === geoId);
      if (bubble) onSelectRef.current(bubble);
    };
    window.addEventListener("hummingbird:select-bubble", handler);
    return () => window.removeEventListener("hummingbird:select-bubble", handler);
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (map.getSource("bubbles")) {
      applyBubbles(map, bubbles);
      return;
    }

    const onLoad = () => applyBubbles(map, bubblesRef.current);
    map.once("load", onLoad);
    return () => {
      map.off("load", onLoad);
    };
  }, [bubbles]);

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

  return <div ref={containerRef} className="h-full w-full" />;
}
