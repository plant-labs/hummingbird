"use client";

import type { IncidentSummary } from "@/lib/types";
import { outcomeTone, statusLabel, verificationLabel, verificationTone } from "@/lib/labels";

type Props = {
  placeName: string;
  state: string;
  count: number;
  incidents: IncidentSummary[];
  loading: boolean;
  onSelectIncident: (id: string) => void;
  onClose: () => void;
};

export default function IncidentListPanel({
  placeName,
  state,
  count,
  incidents,
  loading,
  onSelectIncident,
  onClose,
}: Props) {
  return (
    <aside className="pointer-events-auto flex h-full w-full max-w-md flex-col border-l border-ink/10 bg-mist/95 shadow-[-16px_0_40px_rgba(20,32,27,0.12)] backdrop-blur-md">
      <header className="flex items-start justify-between gap-3 border-b border-ink/10 px-5 py-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-moss/70">Location</p>
          <h2 className="font-display text-2xl leading-tight text-ink">{placeName}</h2>
          <p className="mt-1 text-sm text-ink/70">
            {state} · {count} published incident{count === 1 ? "" : "s"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-sm text-ink/60 transition hover:text-ink"
          aria-label="Close panel"
        >
          Close
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {loading && <p className="px-2 py-6 text-sm text-ink/60">Loading incidents…</p>}
        {!loading && incidents.length === 0 && (
          <p className="px-2 py-6 text-sm text-ink/60">No published incidents for this place.</p>
        )}
        <ul className="space-y-2">
          {incidents.map((inc) => {
            const vTone = verificationTone(inc.verification_status);
            const oTone = outcomeTone(inc.current_status);
            return (
              <li key={inc.incident_id}>
                <button
                  type="button"
                  onClick={() => onSelectIncident(inc.incident_id)}
                  className="w-full border border-ink/10 bg-white/70 px-4 py-3 text-left transition hover:border-fern/40 hover:bg-white"
                >
                  <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-wide text-ink/55">
                    <span>{inc.event_type}</span>
                    <span>{inc.date_reported}</span>
                  </div>
                  <p className="mt-1 font-medium text-ink">{inc.headline || "Untitled incident"}</p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    <span className={`${vTone.bg} ${vTone.text} px-2 py-0.5`}>
                      {verificationLabel(inc.verification_status)}
                      {inc.corroboration_count > 0 ? ` · ${inc.corroboration_count} sources` : ""}
                    </span>
                    <span className={`${oTone.bg} ${oTone.text} px-2 py-0.5`}>
                      {statusLabel(inc.current_status)}
                    </span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </aside>
  );
}
