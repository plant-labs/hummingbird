"use client";

import type { IncidentDetail } from "@/lib/types";
import { statusLabel, verificationLabel } from "@/lib/labels";

type Props = {
  detail: IncidentDetail | null;
  loading: boolean;
  onBack: () => void;
};

export default function IncidentDetailPanel({ detail, loading, onBack }: Props) {
  return (
    <aside className="pointer-events-auto flex h-full w-full max-w-md flex-col border-l border-ink/10 bg-mist/95 shadow-[-16px_0_40px_rgba(20,32,27,0.12)] backdrop-blur-md">
      <header className="border-b border-ink/10 px-5 py-4">
        <button type="button" onClick={onBack} className="text-sm text-fern hover:underline">
          ← Back to list
        </button>
        {detail && (
          <>
            <p className="mt-3 text-xs uppercase tracking-[0.18em] text-moss/70">{detail.event_type}</p>
            <h2 className="font-display text-2xl leading-tight text-ink">
              {detail.headline || "Incident"}
            </h2>
            <p className="mt-1 text-sm text-ink/70">
              {[detail.lga, detail.state].filter(Boolean).join(", ")} · reported {detail.date_reported}
            </p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="bg-fern/10 px-2 py-0.5 text-fern">
                {verificationLabel(detail.verification_status)}
                {detail.corroboration_count > 0 ? ` · ${detail.corroboration_count} sources` : ""}
              </span>
              <span className="bg-alert/10 px-2 py-0.5 text-alert">
                {statusLabel(detail.current_status)}
              </span>
            </div>
          </>
        )}
      </header>

      <div className="flex-1 space-y-6 overflow-y-auto px-5 py-4">
        {loading && <p className="text-sm text-ink/60">Loading detail…</p>}
        {detail && (
          <>
            <section>
              <h3 className="text-xs uppercase tracking-[0.16em] text-moss/70">Cited facts</h3>
              {detail.fields.length === 0 ? (
                <p className="mt-2 text-sm text-ink/60">No structured fields yet.</p>
              ) : (
                <ul className="mt-2 space-y-3">
                  {detail.fields.map((f, idx) => (
                    <li key={`${f.field_name}-${idx}`} className="border-b border-ink/5 pb-3">
                      <p className="text-xs uppercase tracking-wide text-ink/50">{f.field_name}</p>
                      <p className="font-medium text-ink">{String(f.value)}</p>
                      <p className="mt-1 text-xs italic text-ink/55">&ldquo;{f.source_span}&rdquo;</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h3 className="text-xs uppercase tracking-[0.16em] text-moss/70">Status history</h3>
              {detail.status_history.length === 0 ? (
                <p className="mt-2 text-sm text-ink/60">No status transitions recorded.</p>
              ) : (
                <ol className="mt-2 space-y-3 border-l border-fern/30 pl-4">
                  {detail.status_history.map((s, idx) => (
                    <li key={`${s.to_status}-${idx}`}>
                      <p className="font-medium text-ink">{statusLabel(s.to_status)}</p>
                      <p className="text-xs text-ink/55">
                        {new Date(s.changed_at).toLocaleString()}
                        {s.note ? ` — ${s.note}` : ""}
                      </p>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section>
              <h3 className="text-xs uppercase tracking-[0.16em] text-moss/70">Sources</h3>
              <ul className="mt-2 space-y-3">
                {detail.sources.map((s) => (
                  <li key={s.source.source_id} className="bg-white/60 p-3">
                    <div className="flex items-center justify-between gap-2 text-xs uppercase tracking-wide text-ink/50">
                      <span>{s.source.outlet}</span>
                      <span>{s.role}</span>
                    </div>
                    <p className="mt-1 text-sm text-ink/80">{s.source.excerpt}</p>
                    <a
                      href={s.source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-block text-sm text-signal underline-offset-2 hover:underline"
                    >
                      Open original source
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          </>
        )}
      </div>
    </aside>
  );
}
