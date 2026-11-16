export type CalendarFields = {
  title: string; description: string; starts_at: string; ends_at: string; location: string;
};

/** Only pass the event's public projection. Ticket tokens and member data never leave the site. */
export function googleCalendarUrl(event: CalendarFields) {
  const stamp = (value: string) => new Date(value).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const query = new URLSearchParams({
    action: "TEMPLATE", text: event.title, dates: `${stamp(event.starts_at)}/${stamp(event.ends_at)}`,
    details: event.description, location: event.location,
  });
  return `https://calendar.google.com/calendar/render?${query}`;
}

export function saveTicketBlob(blob: Blob, title: string) {
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a"); link.href = url;
    link.download = `${title.replace(/[^A-Za-z0-9._-]+/g, "-") || "event"}-ticket.png`;
    link.click();
  } finally { URL.revokeObjectURL(url); }
}
