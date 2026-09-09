"use client";

import { useEffect, useState } from "react";
import { approveReview, fetchReviewQueue, rejectReview } from "@/lib/api";
import type { ReviewItem } from "@/lib/types";
import Link from "next/link";

export default function ModerationQueue() {
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = async () => {
    try {
      setItems(await fetchReviewQueue());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load queue");
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onApprove = async (id: string) => {
    setBusy(id);
    try {
      await approveReview(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setBusy(null);
    }
  };

  const onReject = async (id: string) => {
    setBusy(id);
    try {
      await rejectReview(id, "Rejected by moderator");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <main className="min-h-screen px-5 py-8 md:px-10">
      <div className="mx-auto max-w-3xl pt-10">
        <Link href="/" className="text-sm text-fern hover:underline">
          ← Map
        </Link>
        <h1 className="mt-3 font-display text-4xl text-ink">Review queue</h1>
        <p className="mt-2 max-w-2xl text-sm text-ink/70">
          Human gate before publish. Casualty and headcount fields always land here. Approving
          elevates a candidate onto the public map with source citations.
        </p>
        {error && <p className="mt-4 text-sm text-alert">{error}</p>}

        <ul className="mt-8 space-y-4">
          {items.length === 0 && (
            <li className="border border-ink/10 bg-white/50 px-4 py-6 text-sm text-ink/60">
              No pending items.
            </li>
          )}
          {items.map((item) => {
            const preview = item.candidate_json?.publish_preview || {};
            const tip = item.candidate_json?.tip;
            const isCrowd = item.candidate_json?.route === "crowd_tip";
            return (
              <li key={item.queue_id} className="border border-ink/10 bg-white/70 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.16em] text-moss/70">
                      {preview.event_type || "unknown"} · priority {item.priority}
                      {isCrowd ? " · crowd tip" : ""}
                    </p>
                    <h2 className="mt-1 font-display text-2xl text-ink">
                      {preview.headline || "Untitled candidate"}
                    </h2>
                    <p className="mt-1 text-sm text-ink/70">
                      {[preview.lga, preview.state].filter(Boolean).join(", ")}
                      {preview.verification_status
                        ? ` · ${preview.verification_status}`
                        : ""}
                      {preview.corroboration_count != null
                        ? ` · ${preview.corroboration_count} outlets`
                        : ""}
                    </p>
                    {item.reason && (
                      <p className="mt-2 text-sm text-ink/60">{item.reason}</p>
                    )}
                    {tip?.description && (
                      <p className="mt-3 text-sm leading-relaxed text-ink/75">{tip.description}</p>
                    )}
                    <div className="mt-2 space-y-1 text-xs text-ink/55">
                      {preview.source_url && (
                        <p>
                          Source:{" "}
                          <a
                            href={preview.source_url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-fern underline-offset-2 hover:underline"
                          >
                            {preview.source_url}
                          </a>
                        </p>
                      )}
                      {tip?.attachment && (
                        <p>
                          Attachment: {tip.attachment.filename || "file"}
                          {tip.attachment.size != null
                            ? ` (${Math.round(tip.attachment.size / 1024)} KB)`
                            : ""}
                        </p>
                      )}
                      {(tip?.contact_email || tip?.contact_name) && (
                        <p>
                          Contact: {[tip.contact_name, tip.contact_email].filter(Boolean).join(" · ")}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy === item.queue_id}
                      onClick={() => onApprove(item.queue_id)}
                      className="bg-fern px-3 py-2 text-sm text-mist disabled:opacity-50"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      disabled={busy === item.queue_id}
                      onClick={() => onReject(item.queue_id)}
                      className="border border-ink/20 px-3 py-2 text-sm text-ink disabled:opacity-50"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </main>
  );
}
