import AppMenu from "@/components/AppMenu";
import ReportIncidentForm from "@/components/ReportIncidentForm";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Report an incident · Hummingbird",
  description: "Submit a tip for investigation. Crowd reports never auto-publish.",
};

export default function ReportPage() {
  return (
    <main className="relative min-h-screen px-5 py-8 md:px-10 md:py-10">
      <div className="absolute left-5 top-5 z-40 md:left-8 md:top-7">
        <AppMenu />
      </div>

      <div className="mx-auto max-w-2xl pt-14">
        <p className="text-xs uppercase tracking-[0.22em] text-moss/80">Tip line</p>
        <h1 className="mt-2 font-display text-4xl text-ink md:text-5xl">Report an incident</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink/75 md:text-base">
          Submissions go to our review queue for investigation. They are not published until
          sources are checked. Please add proof — a URL or attachment — whenever you can.
        </p>

        <div className="mt-8">
          <ReportIncidentForm />
        </div>
      </div>
    </main>
  );
}
