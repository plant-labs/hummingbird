"use client";

import { useCallback, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  fetchBubbleIncidents,
  fetchBubbles,
  fetchIncident,
  API_BASE,
} from "@/lib/api";
import type { GeoBubble, IncidentDetail, IncidentSummary } from "@/lib/types";
import IncidentListPanel from "./IncidentListPanel";
import IncidentDetailPanel from "./IncidentDetailPanel";

const HeatMap = dynamic(() => import("./HeatMap"), { ssr: false });

export default function MapExplorer() {
  const [bubbles, setBubbles] = useState<GeoBubble[]>([]);
  const [selected, setSelected] = useState<GeoBubble | null>(null);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [listLoading, setListLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveNote, setLiveNote] = useState("Connecting…");

  const loadBubbles = useCallback(async () => {
    try {
      const data = await fetchBubbles("lga");
      setBubbles(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load map data");
    }
  }, []);

  useEffect(() => {
    loadBubbles();
  }, [loadBubbles]);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/stream`);
    es.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data);
        if (payload.event === "connected") {
          setLiveNote(payload.store === "demo" ? "Live · demo store" : "Live · postgres");
        } else if (payload.event === "bubble_refresh" || payload.event === "incident_changes") {
          loadBubbles();
        } else if (payload.event === "heartbeat") {
          setLiveNote((n) => (n.startsWith("Live") ? n : "Live"));
        }
      } catch {
        /* ignore */
      }
    };
    es.onerror = () => setLiveNote("Offline");
    return () => es.close();
  }, [loadBubbles]);

  const onSelectBubble = async (bubble: GeoBubble) => {
    setSelected(bubble);
    setDetail(null);
    setListLoading(true);
    try {
      const rows = await fetchBubbleIncidents(bubble.geo_id);
      setIncidents(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incidents");
    } finally {
      setListLoading(false);
    }
  };

  const onSelectIncident = async (id: string) => {
    setDetailLoading(true);
    try {
      const d = await fetchIncident(id);
      setDetail(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incident");
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden">
      <div className="absolute inset-0">
        <HeatMap
          bubbles={bubbles}
          selectedGeoId={selected?.geo_id}
          onSelect={onSelectBubble}
        />
      </div>

      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-mist/80 via-transparent to-transparent" />

      <header className="pointer-events-none absolute left-0 right-0 top-0 z-10 px-5 pt-5 md:px-8 md:pt-7">
        <div className="pointer-events-auto max-w-xl">
          <p className="text-xs uppercase tracking-[0.22em] text-moss/80">Nigeria · security intelligence</p>
          <h1 className="font-display text-4xl text-ink md:text-5xl">Hummingbird</h1>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-ink/75 md:text-base">
            Live incidents across 36 states — every claim grounded in a source. Click a heat
            bubble to explore.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink/60">
            <span className="inline-flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-signal" />
              {liveNote}
            </span>
            <span>{bubbles.reduce((n, b) => n + b.count, 0)} published</span>
            <a href="/moderation" className="pointer-events-auto text-fern underline-offset-2 hover:underline">
              Moderation
            </a>
          </div>
          {error && <p className="mt-2 text-sm text-alert">{error}</p>}
        </div>
      </header>

      <div className="pointer-events-none absolute bottom-4 left-4 z-10 flex gap-3 text-[11px] text-ink/70 md:bottom-6 md:left-6">
        <LegendDot color="#c45c26" label="Reported" />
        <LegendDot color="#2f6b4f" label="Verified" />
        <LegendDot color="#0e7c6b" label="Official" />
      </div>

      {(selected || detail) && (
        <div className="absolute bottom-0 right-0 top-0 z-20 flex w-full max-w-md justify-end md:max-w-md">
          {detail || detailLoading ? (
            <IncidentDetailPanel
              detail={detail}
              loading={detailLoading}
              onBack={() => setDetail(null)}
            />
          ) : selected ? (
            <IncidentListPanel
              placeName={selected.name}
              state={selected.state}
              count={selected.count}
              incidents={incidents}
              loading={listLoading}
              onSelectIncident={onSelectIncident}
              onClose={() => {
                setSelected(null);
                setIncidents([]);
              }}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded bg-mist/90 px-2 py-1 backdrop-blur">
      <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
