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

export function bubbleColor(status?: string | null): string {
  switch (status) {
    case "official_confirmation":
      return "#0e7c6b";
    case "verified":
      return "#2f6b4f";
    case "reported":
      return "#c45c26";
    default:
      return "#8a7a5c";
  }
}
