"use client";

import { FormEvent, useState, type ReactNode } from "react";
import { submitIncidentReport } from "@/lib/api";
import { EVENT_TYPES, INCIDENT_STATUSES, NIGERIA_STATES } from "@/lib/states";

const MAX_ATTACHMENT_BYTES = 4 * 1024 * 1024;

export default function ReportIncidentForm() {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queueId, setQueueId] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setQueueId(null);

    const form = e.currentTarget;
    const fd = new FormData(form);
    const file = fd.get("attachment");
    if (file instanceof File && file.size > 0) {
      if (file.size > MAX_ATTACHMENT_BYTES) {
        setError("Attachment must be 4 MB or smaller.");
        return;
      }
    } else {
      fd.delete("attachment");
    }

    setSubmitting(true);
    try {
      const result = await submitIncidentReport(fd);
      setQueueId(result.queue_id);
      form.reset();
      setFileName(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (queueId) {
    return (
      <div className="border border-fern/30 bg-white/70 p-6">
        <p className="text-xs uppercase tracking-[0.18em] text-fern">Received</p>
        <h2 className="mt-2 font-display text-2xl text-ink">Thank you — we will investigate</h2>
        <p className="mt-3 text-sm leading-relaxed text-ink/75">
          Your tip is in the review queue and will not appear on the public map until a moderator
          corroborates it. Crowd reports never auto-publish.
        </p>
        <p className="mt-3 font-mono text-xs text-ink/50">Reference: {queueId}</p>
        <button
          type="button"
          className="mt-6 bg-fern px-4 py-2 text-sm text-mist"
          onClick={() => setQueueId(null)}
        >
          Submit another report
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-8" encType="multipart/form-data">
      <section className="space-y-4 border border-ink/10 bg-white/60 p-5 md:p-6">
        <div>
          <h2 className="font-display text-xl text-ink">What happened</h2>
          <p className="mt-1 text-sm text-ink/65">
            Required fields match what moderators need before anything can enter the database.
          </p>
        </div>

        <Field label="Event type" htmlFor="event_type" required>
          <select id="event_type" name="event_type" required className={inputClass} defaultValue="kidnap">
            {EVENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Headline" htmlFor="headline" required hint="Short public-facing summary">
          <input
            id="headline"
            name="headline"
            required
            maxLength={200}
            className={inputClass}
            placeholder="e.g. Travelers abducted near highway checkpoint"
          />
        </Field>

        <Field
          label="Description"
          htmlFor="description"
          required
          hint="What happened, where, when — this becomes the citation excerpt"
        >
          <textarea
            id="description"
            name="description"
            required
            rows={5}
            maxLength={8000}
            className={inputClass}
            placeholder="Describe the incident with as much verifiable detail as you can."
          />
        </Field>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="State" htmlFor="state" required>
            <select id="state" name="state" required className={inputClass} defaultValue="">
              <option value="" disabled>
                Select state
              </option>
              {NIGERIA_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Date reported" htmlFor="date_reported" required>
            <input
              id="date_reported"
              name="date_reported"
              type="date"
              required
              className={inputClass}
              defaultValue={new Date().toISOString().slice(0, 10)}
            />
          </Field>
        </div>
      </section>

      <section className="space-y-4 border border-ink/10 bg-white/60 p-5 md:p-6">
        <div>
          <h2 className="font-display text-xl text-ink">Location & timing</h2>
          <p className="mt-1 text-sm text-ink/65">Optional fields — add them if known.</p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="LGA" htmlFor="lga" optional>
            <input id="lga" name="lga" className={inputClass} placeholder="Local Government Area" />
          </Field>
          <Field label="Date occurred" htmlFor="date_occurred" optional>
            <input id="date_occurred" name="date_occurred" type="date" className={inputClass} />
          </Field>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Latitude" htmlFor="lat" optional>
            <input id="lat" name="lat" type="number" step="any" className={inputClass} placeholder="e.g. 9.0765" />
          </Field>
          <Field label="Longitude" htmlFor="lng" optional>
            <input id="lng" name="lng" type="number" step="any" className={inputClass} placeholder="e.g. 7.3986" />
          </Field>
        </div>

        <Field label="Current status" htmlFor="current_status" optional>
          <select id="current_status" name="current_status" className={inputClass} defaultValue="ongoing">
            {INCIDENT_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </Field>
      </section>

      <section className="space-y-4 border border-ink/10 bg-white/60 p-5 md:p-6">
        <div>
          <h2 className="font-display text-xl text-ink">People affected</h2>
          <p className="mt-1 text-sm text-ink/65">
            Prefer aggregates (e.g. travelers, students). Do not include victim names unless
            officially released.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Victim count" htmlFor="victim_count" optional>
            <input id="victim_count" name="victim_count" type="number" min={0} className={inputClass} />
          </Field>
          <Field label="Victim type" htmlFor="victim_type" optional>
            <input
              id="victim_type"
              name="victim_type"
              className={inputClass}
              placeholder="e.g. travelers, students"
            />
          </Field>
        </div>
      </section>

      <section className="space-y-4 border border-alert/25 bg-alert/5 p-5 md:p-6">
        <div>
          <h2 className="font-display text-xl text-ink">Proof of the incident</h2>
          <p className="mt-1 text-sm leading-relaxed text-ink/75">
            Strongly encouraged. Attach a news clipping, police statement, community notice, or
            screenshot of a verified report — or paste a source URL. Tips without corroborating
            material are harder to investigate and less likely to be published.
          </p>
        </div>

        <Field label="Source URL" htmlFor="source_url" optional hint="News article, official statement, or social post">
          <input
            id="source_url"
            name="source_url"
            type="url"
            className={inputClass}
            placeholder="https://"
          />
        </Field>

        <Field
          label="Attachment"
          htmlFor="attachment"
          optional
          hint="Image or PDF, max 4 MB — police flyer, news screenshot, etc."
        >
          <input
            id="attachment"
            name="attachment"
            type="file"
            accept="image/*,.pdf,application/pdf"
            className="block w-full text-sm text-ink/80 file:mr-3 file:border-0 file:bg-fern file:px-3 file:py-2 file:text-sm file:text-mist"
            onChange={(ev) => {
              const f = ev.target.files?.[0];
              setFileName(f ? f.name : null);
            }}
          />
          {fileName && <p className="mt-1 text-xs text-ink/55">Selected: {fileName}</p>}
        </Field>
      </section>

      <section className="space-y-4 border border-ink/10 bg-white/60 p-5 md:p-6">
        <div>
          <h2 className="font-display text-xl text-ink">Contact</h2>
          <p className="mt-1 text-sm text-ink/65">
            Optional — only used if we need to follow up. Never published on the map.
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Your name" htmlFor="contact_name" optional>
            <input id="contact_name" name="contact_name" className={inputClass} autoComplete="name" />
          </Field>
          <Field label="Email" htmlFor="contact_email" optional>
            <input
              id="contact_email"
              name="contact_email"
              type="email"
              className={inputClass}
              autoComplete="email"
            />
          </Field>
        </div>
      </section>

      {error && <p className="text-sm text-alert">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="bg-fern px-5 py-3 text-sm font-medium text-mist transition hover:bg-moss disabled:opacity-50"
      >
        {submitting ? "Sending…" : "Submit for investigation"}
      </button>
    </form>
  );
}

const inputClass =
  "mt-1 w-full border border-ink/15 bg-mist/80 px-3 py-2 text-sm text-ink outline-none focus:border-fern";

function Field({
  label,
  htmlFor,
  children,
  required,
  optional,
  hint,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
  required?: boolean;
  optional?: boolean;
  hint?: string;
}) {
  return (
    <label htmlFor={htmlFor} className="block">
      <span className="text-sm font-medium text-ink">
        {label}
        {required && <span className="text-alert"> *</span>}
        {optional && (
          <span className="ml-2 text-xs font-normal uppercase tracking-wide text-ink/45">
            Optional
          </span>
        )}
      </span>
      {hint && <span className="mt-0.5 block text-xs text-ink/50">{hint}</span>}
      {children}
    </label>
  );
}
