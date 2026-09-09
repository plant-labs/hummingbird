"use client";

import HummingbirdMark from "@/components/HummingbirdMark";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

const LINKS = [
  { href: "/", label: "Map" },
  { href: "/report", label: "Report an incident" },
  { href: "/about", label: "About us" },
  { href: "/moderation", label: "Moderation" },
] as const;

export default function AppMenu() {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointer = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="pointer-events-auto relative z-40">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((v) => !v)}
        className="flex h-11 w-11 flex-col items-center justify-center gap-1.5 border border-ink/15 bg-mist/95 text-ink shadow-sm backdrop-blur transition hover:border-fern/40"
      >
        <span
          className={`block h-0.5 w-5 bg-current transition ${open ? "translate-y-2 rotate-45" : ""}`}
        />
        <span className={`block h-0.5 w-5 bg-current transition ${open ? "opacity-0" : ""}`} />
        <span
          className={`block h-0.5 w-5 bg-current transition ${open ? "-translate-y-2 -rotate-45" : ""}`}
        />
      </button>

      {open && (
        <nav
          id={panelId}
          className="absolute left-0 top-12 w-56 border border-ink/10 bg-mist/98 py-2 shadow-lg backdrop-blur"
        >
          <p className="flex items-center gap-2 px-4 pb-2 pt-1 text-[10px] uppercase tracking-[0.2em] text-moss/70">
            <HummingbirdMark size={16} />
            Hummingbird
          </p>
          <ul>
            {LINKS.map((link) => (
              <li key={link.href}>
                <Link
                  href={link.href}
                  onClick={() => setOpen(false)}
                  className="block px-4 py-2.5 text-sm text-ink transition hover:bg-fern/10 hover:text-fern"
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
