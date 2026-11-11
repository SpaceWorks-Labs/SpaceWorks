import { t } from "@lingui/core/macro";
import { useContext } from "react";
import { useMutation } from "@tanstack/react-query";

import { ErrorText } from "../../../components/ui";
import { staffRequestBlob } from "../../../lib/api";
import { StaffListContext } from "../StaffListContext";

/**
 * EB1: the guest list as CSV from the Registrations tab, for anyone holding manage_registrations
 * on the event (co-organizers included), not only behind Teams and projects. The export takes the
 * roster's status and search filters; it needs the `events.saved_views` switch the server checks.
 */
export function GuestCsvButton(props: { eventId: number; status?: string; q?: string }) {
  const { makerspace } = useContext(StaffListContext);
  return (makerspace?.enabled_features ?? []).includes("events.saved_views") ? <GuestCsvExport {...props} /> : null;
}

function GuestCsvExport({ eventId, status, q }: { eventId: number; status?: string; q?: string }) {
  const exportCsv = useMutation({ mutationFn: async () => {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    if (q) query.set("q", q);
    const blob = await staffRequestBlob(`/admin/events/${eventId}/lists/guests/export/${query.toString() ? `?${query}` : ""}`);
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `event-${eventId}-guests.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  } });
  return <div className="mb-4 grid gap-1">
    <button type="button" className="desk-button w-fit" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
      {exportCsv.isPending ? t`Preparing guest list…` : status || q ? t`Download these guests (CSV)` : t`Download guest list (CSV)`}</button>
    {exportCsv.error ? <ErrorText message={t`Couldn't download the guest list. Try again.`} /> : null}
  </div>;
}
