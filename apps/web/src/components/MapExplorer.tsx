"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  fetchBubbleIncidents,
  fetchBubbles,
  fetchIncident,
  searchIncidents,
  API_BASE,
  type DateRangeFilter,
} from "@/lib/api";
import type { GeoBubble, IncidentDetail, IncidentSummary } from "@/lib/types";
import AppMenu from "./AppMenu";
import HummingbirdMark from "./HummingbirdMark";
import IncidentListPanel from "./IncidentListPanel";
import IncidentDetailPanel from "./IncidentDetailPanel";
import LoadingIndicator from "./LoadingIndicator";

const HeatMap = dynamic(() => import("./HeatMap"), { ssr: false });

const dateInputClass =
  "border border-ink/15 bg-mist/95 px-2 py-1.5 text-xs text-ink outline-none backdrop-blur focus:border-fern";

export default function MapExplorer() {
  const [bubbles, setBubbles] = useState<GeoBubble[]>([]);
  const [bubblesLoading, setBubblesLoading] = useState(true);
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
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [focusPoint, setFocusPoint] = useState<{ lat: number; lng: number; key: string } | null>(
    null,
  );
  const searchWrapRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const filterWrapRef = useRef<HTMLDivElement>(null);

  const dateRange: DateRangeFilter = {
    dateFrom: dateFrom || null,
    dateTo: dateTo || null,
  };
  const dateFilterActive = Boolean(dateFrom || dateTo);

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
    setBubblesLoading(true);
    try {
      const data = await fetchBubbles("lga", {
        dateFrom: dateFrom || null,
        dateTo: dateTo || null,
      });
      setBubbles(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load map data");
    } finally {
      setBubblesLoading(false);
    }
  }, [dateFrom, dateTo]);

  useEffect(() => {
    loadBubbles();
  }, [loadBubbles]);

  useEffect(() => {
    // Date range change invalidates open list/detail (counts no longer match).
    setSelected(null);
    setDetail(null);
    setIncidents([]);
    setSearchActive(false);
    setSearchLabel("");
    setSearchQuery("");
    setSearchOpen(false);
    setFocusPoint(null);
  }, [dateFrom, dateTo]);

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
    if (!filterOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFilterOpen(false);
    };
    // Do not close on outside mousedown — the native date picker popup lives
    // outside this DOM tree, and closing early cancels the date selection.
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [filterOpen]);

  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/stream`);
    es.onmessage = (msg) => {
      try {
        const payload = JSON.parse(msg.data);
        if (payload.event === "connected") {
          setLiveNote("Live");
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
        const rows = await searchIncidents(q, 20, {
          dateFrom: dateFrom || null,
          dateTo: dateTo || null,
        });
        setIncidents(rows);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Search failed");
      } finally {
        setListLoading(false);
      }
    }, 250);

    return () => window.clearTimeout(handle);
  }, [searchQuery, dateFrom, dateTo]);

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
      const rows = await fetchBubbleIncidents(bubble.geo_id, dateRange);
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
                    strokeLinejoin="round"
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
            <div ref={filterWrapRef} className="relative">
              <button
                type="button"
                aria-label="Filter by date"
                aria-expanded={filterOpen}
                onClick={() => setFilterOpen((open) => !open)}
                className={`relative flex h-11 w-11 items-center justify-center border bg-mist/95 text-ink shadow-sm backdrop-blur transition hover:border-fern/40 ${
                  filterOpen || dateFilterActive ? "border-fern/50" : "border-ink/15"
                }`}
              >
                <svg
                  width="18"
                  height="18"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden
                >
                  <path d="M4 5h16l-6 7v5l-4 2v-7L4 5z" />
                </svg>
                {dateFilterActive && (
                  <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-fern" />
                )}
              </button>
              {filterOpen && (
                <div className="absolute left-0 top-full z-30 mt-2 w-56 border border-ink/10 bg-mist/95 p-3 shadow-lg backdrop-blur">
                  <p className="text-[10px] uppercase tracking-[0.14em] text-moss/70">
                    Occurrence period
                  </p>
                  <div className="mt-2 flex flex-col gap-2">
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] text-ink/55">From</span>
                      <input
                        type="date"
                        value={dateFrom}
                        max={dateTo || undefined}
                        onChange={(e) => setDateFrom(e.target.value)}
                        className={dateInputClass}
                      />
                    </label>
                    <label className="flex flex-col gap-1">
                      <span className="text-[11px] text-ink/55">To</span>
                      <input
                        type="date"
                        value={dateTo}
                        min={dateFrom || undefined}
                        onChange={(e) => setDateTo(e.target.value)}
                        className={dateInputClass}
                      />
                    </label>
                  </div>
                  <p className="mt-2 text-[11px] leading-snug text-ink/45">
                    Uses occurrence date; falls back to reported if unknown.
                  </p>
                  <div className="mt-3 flex items-center justify-between gap-2">
                    {dateFilterActive ? (
                      <button
                        type="button"
                        onClick={() => {
                          setDateFrom("");
                          setDateTo("");
                        }}
                        className="text-xs text-fern underline-offset-2 hover:underline"
                      >
                        Clear dates
                      </button>
                    ) : (
                      <span />
                    )}
                    <button
                      type="button"
                      onClick={() => setFilterOpen(false)}
                      className="border border-ink/15 bg-white/70 px-2.5 py-1 text-xs text-ink transition hover:border-fern/40"
                    >
                      Done
                    </button>
                  </div>
                </div>
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
              {bubblesLoading ? (
                <LoadingIndicator size="sm" label="Loading map…" />
              ) : (
                <>
                  <span>
                    {bubbles.reduce((n, b) => n + b.count, 0)} published
                    {dateFilterActive ? " in range" : ""}
                  </span>
                  {bubbles.length === 0 && !error && (
                    <span>
                      {dateFilterActive
                        ? "No incidents in this date range"
                        : "No published incidents yet"}
                    </span>
                  )}
                </>
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
