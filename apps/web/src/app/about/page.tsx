import AppMenu from "@/components/AppMenu";
import HummingbirdMark from "@/components/HummingbirdMark";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "About us · Hummingbird",
  description: "Open-source security intelligence for Nigeria — sourced, verified, live.",
};

export default function AboutPage() {
  return (
    <main className="relative min-h-screen px-5 py-8 md:px-10 md:py-10">
      <div className="absolute left-5 top-5 z-40 md:left-8 md:top-7">
        <AppMenu />
      </div>

      <article className="mx-auto max-w-2xl pt-14">
        <p className="text-xs uppercase tracking-[0.22em] text-moss/80">About</p>
        <div className="mt-2 flex items-center gap-3">
          <HummingbirdMark size={48} priority />
          <h1 className="font-display text-4xl text-ink md:text-5xl">Hummingbird</h1>
        </div>
        <p className="mt-4 text-base leading-relaxed text-ink/80 md:text-lg">
          Hummingbird is an open-source security intelligence platform for Nigeria. We track
          kidnappings, robberies, terrorism, protests, scams, and related events on a live map —
          with every published claim grounded in a source.
        </p>

        <section className="mt-10 space-y-3">
          <h2 className="font-display text-2xl text-ink">How we work</h2>
          <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-ink/75 md:text-base">
            <li>
              <strong className="font-medium text-ink">Reported ≠ verified.</strong> Records move
              through explicit verification states; unverified tips never appear as flat fact.
            </li>
            <li>
              <strong className="font-medium text-ink">No source, no field.</strong> Published facts
              carry citations (URL, outlet, excerpt).
            </li>
            <li>
              <strong className="font-medium text-ink">Crowd tips need review.</strong> Public
              submissions enter a moderation queue and never auto-publish alone.
            </li>
            <li>
              We prefer aggregated victim types over names, and we do not publish victim photos
              unless released through official channels.
            </li>
          </ul>
        </section>

        <section className="mt-10 space-y-3">
          <h2 className="font-display text-2xl text-ink">Help us improve coverage</h2>
          <p className="text-sm leading-relaxed text-ink/75 md:text-base">
            If you know about an incident that is not on the map,{" "}
            <Link href="/report" className="text-fern underline-offset-2 hover:underline">
              report it with proof
            </Link>
            . News links, police statements, and community notices help us investigate faster.
          </p>
        </section>

        <p className="mt-12 text-sm text-ink/55">
          <Link href="/" className="text-fern hover:underline">
            ← Back to the map
          </Link>
        </p>
      </article>
    </main>
  );
}
