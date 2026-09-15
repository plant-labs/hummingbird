"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  fetchBubbleIncidents,
  fetchBubbles,
  fetchIncident,
  searchIncidents,
  API_BASE,
} from "@/lib/api";
import type { GeoBubble, IncidentDetail, IncidentSummary } from "@/lib/types";
import AppMenu from "./AppMenu";
import HummingbirdMark from "./HummingbirdMark";
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
  const [searchQuery, setSearchQuery] = useState("");
  const [searchActive, setSearchActive] = useState(false);
  const [searchLabel, setSearchLabel] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [focusPoint, setFocusPoint] = useState<{ lat: number; lng: number; key: string } | null>(
    null,
  );
  const searchWrapRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  const collapseSearch = useCallback(() => {
    setSearchOpen(false);
    setSearchQuery("");
    setSearchActive(false);
    setSearchLabel("");
    if (searchActive) {
      setIncidents([]);
      setDetail(null);
      setSelected(null);
      setFocusPoint(null);
    }
  }, [searchActive]);

  const clearPanels = useCallback(() => {
    setSelected(null);
    setDetail(null);
    setIncidents([]);
    setDetailLoading(false);
    setSearchActive(false);
    setSearchLabel("");
    setSearchQuery("");
    setSearchOpen(false);
    setFocusPoint(null);
  }, []);

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
    window.addEventListener("hummingbird:dismiss-panel", clearPanels);
    return () => window.removeEventListener("hummingbird:dismiss-panel", clearPanels);
  }, [clearPanels]);

  useEffect(() => {
    if (!searchOpen) return;
    searchInputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") collapseSearch();
    };
    const onPointer = (e: MouseEvent) => {
      if (searchWrapRef.current?.contains(e.target as Node)) return;
      // Keep results panel usable — only fold the input back to an icon.
      if (searchActive) {
        setSearchOpen(false);
        return;
      }
      collapseSearch();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [searchOpen, searchActive, collapseSearch]);

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

  useEffect(() => {
    const q = searchQuery.trim();
    if (q.length < 2) {
      if (searchActive && q.length === 0) {
        setSearchActive(false);
        setSearchLabel("");
        setIncidents([]);
        setListLoading(false);
      }
      return;
    }

    const handle = window.setTimeout(async () => {
      setSearchActive(true);
      setSelected(null);
      setDetail(null);
      setSearchLabel(q);
      setListLoading(true);
      try {
        const rows = await searchIncidents(q);
        setIncidents(rows);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
      } finally {
        setListLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(handle);
  }, [searchQuery]);

  const onSelectBubble = async (bubble: GeoBubble) => {
    setSearchActive(false);
    setSearchLabel("");
    setSearchQuery("");
    setSearchOpen(false);
    setFocusPoint(null);
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
      if (
        d.lat != null &&
        d.lng != null &&
        Number.isFinite(Number(d.lat)) &&
        Number.isFinite(Number(d.lng))
      ) {
        setFocusPoint({
          lat: Number(d.lat),
          lng: Number(d.lng),
          key: `${d.incident_id}-${Date.now()}`,
        });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load incident");
    } finally {
      setDetailLoading(false);
    }
  };

  const showPanel = Boolean(selected || detail || searchActive);

  return (
    <div className="relative h-[100dvh] w-full overflow-hidden">
      <div className="absolute inset-0">
        <HeatMap
          bubbles={bubbles}
          selectedGeoId={selected?.geo_id}
          focusPoint={focusPoint}
          onSelect={onSelectBubble}
        />
      </div>

      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-mist/80 via-transparent to-transparent" />

      <header className="pointer-events-none absolute left-0 right-0 top-0 z-10 px-5 pt-5 md:px-8 md:pt-7">
        <div className="flex items-start gap-4">
          <div className="pointer-events-auto flex flex-col items-start gap-2">
            <AppMenu />
            <div ref={searchWrapRef}>
              {!searchOpen ? (
                <button
                  type="button"
                  aria-label="Search incidents"
                  onClick={() => setSearchOpen(true)}
                  className="flex h-11 w-11 items-center justify-center border border-ink/15 bg-mist/95 text-ink shadow-sm backdrop-blur transition hover:border-fern/40"
                >
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    aria-hidden
                  >
                    <circle cx="11" cy="11" r="7" />
                    <path d="M20 20l-3.5-3.5" />
                  </svg>
                </button>
              ) : (
                <label className="block w-56 max-w-[min(14rem,calc(100vw-2.5rem))]">
                  <span className="sr-only">Search incidents</span>
                  <input
                    ref={searchInputRef}
                    type="search"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search incidents…"
                    className="w-full border border-ink/15 bg-mist/95 px-2.5 py-2.5 text-sm text-ink outline-none backdrop-blur placeholder:text-ink/40 focus:border-fern"
                  />
                </label>
              )}
            </div>
          </div>
          <div className="pointer-events-auto max-w-xl">
            <p className="text-xs uppercase tracking-[0.22em] text-moss/80">
              Nigeria · security intelligence
            </p>
            <div className="mt-1 flex items-center gap-2.5 md:gap-3">
              <HummingbirdMark size={48} priority />
              <h1 className="font-display text-4xl text-ink md:text-5xl">Hummingbird</h1>
            </div>
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
              {bubbles.length === 0 && !error && (
                <span className="text-alert">No map bubbles yet — check API connection</span>
              )}
            </div>
            {error && <p className="mt-2 text-sm text-alert">{error}</p>}
          </div>
        </div>
      </header>

      <div className="pointer-events-none absolute bottom-4 left-4 z-10 flex gap-3 text-[11px] text-ink/70 md:bottom-6 md:left-6">
        <LegendDot color="#c45c26" label="Captive" />
        <LegendDot color="#2f6b4f" label="Released / rescued" />
      </div>

      {showPanel && (
        <div className="absolute bottom-0 right-0 top-0 z-20 flex w-full max-w-md justify-end md:max-w-md">
          {detail || detailLoading ? (
            <IncidentDetailPanel
              detail={detail}
              loading={detailLoading}
              onBack={() => setDetail(null)}
            />
          ) : searchActive ? (
            <IncidentListPanel
              eyebrow="Search"
              placeName={searchLabel ? `“${searchLabel}”` : "Results"}
              state="Matching published incidents"
              count={incidents.length}
              incidents={incidents}
              loading={listLoading}
              emptyMessage="No published incidents match that search."
              onSelectIncident={onSelectIncident}
              onClose={clearPanels}
            />
          ) : selected ? (
            <IncidentListPanel
              placeName={selected.name}
              state={selected.state}
              count={selected.count}
              incidents={incidents}
              loading={listLoading}
              onSelectIncident={onSelectIncident}
              onClose={clearPanels}
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
