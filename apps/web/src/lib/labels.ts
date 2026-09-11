export function verificationLabel(status: string): string {
  switch (status) {
    case "unconfirmed":
      return "Unconfirmed";
    case "reported":
      return "Reported";
    case "verified":
      return "Verified";
    case "official_confirmation":
      return "Official confirmation";
    default:
      return status;
  }
}

export function statusLabel(status: string): string {
  return status.replaceAll("_", " ");
}

/** Map bubble color by release outcome (not verification). */
export function bubbleColor(outcome?: string | null): string {
  switch (outcome) {
    case "resolved":
      return "#2f6b4f"; // released / rescued
    case "captive":
      return "#c45c26"; // still held / ongoing
    default:
      return "#c45c26";
  }
}

export function isResolvedStatus(status?: string | null): boolean {
  return status === "released" || status === "rescued";
}

/** Verification chip colors shown inside report panels. */
export function verificationTone(status?: string | null): { bg: string; text: string } {
  switch (status) {
    case "official_confirmation":
      return { bg: "bg-signal/15", text: "text-signal" };
    case "verified":
      return { bg: "bg-fern/15", text: "text-fern" };
    case "reported":
      return { bg: "bg-alert/15", text: "text-alert" };
    default:
      return { bg: "bg-ink/10", text: "text-ink/60" };
  }
}

export function outcomeTone(status?: string | null): { bg: string; text: string } {
  if (isResolvedStatus(status)) {
    return { bg: "bg-fern/15", text: "text-fern" };
  }
  return { bg: "bg-alert/15", text: "text-alert" };
}
