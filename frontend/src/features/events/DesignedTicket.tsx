import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { memberRequestBlob } from "../../lib/api";
import { BoxArt } from "../../components/BoxSpinner";

const path = (registrationId: number, format: "png" | "pdf") => `/member/event-registrations/${registrationId}/ticket?format=${format}`;

/**
 * The space's designed ticket (parity D17, switch `events.ticket_designs`): the published design for this ticket
 * type, else the event's, else the organisation default, with this registration's check-in QR on it. Shown only
 * while the place is confirmed and not yet checked in; once checked in (or when no design exists, 404, or the
 * server refuses a used ticket, 410) the generic ticket card shows instead.
 */
export function DesignedTicket({ registrationId, eventTitle, enabled, fallback }: {
  registrationId: number; eventTitle: string; enabled: boolean; fallback: ReactNode;
}) {
  const image = useQuery({
    queryKey: ["member", "designed-ticket", registrationId],
    queryFn: () => memberRequestBlob(path(registrationId, "png")),
    enabled, retry: false, staleTime: 60_000, gcTime: 0, refetchOnWindowFocus: false,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!enabled || !image.data) { setUrl(null); return; }
    const next = URL.createObjectURL(image.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [enabled, image.data]);
  const pdf = useMutation({ mutationFn: async () => {
    const blob = await memberRequestBlob(path(registrationId, "pdf"));
    const href = URL.createObjectURL(blob);
    Object.assign(document.createElement("a"), { href, download: `ticket-${registrationId}.pdf` }).click();
    window.setTimeout(() => URL.revokeObjectURL(href), 1000);
  } });
  if (!enabled || !url || image.isError) return <>{fallback}</>;
  return <figure className="grid gap-3">
    <img src={url} alt={t`Your ticket for ${eventTitle}, with your check-in code`}
      className="w-full rounded-xl border border-line bg-panel shadow-[0_6px_20px_-12px_rgb(0_0_0/0.35)]" />
    <figcaption className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
      <span>{t`Show this at check-in. It stops working once you are checked in.`}</span>
      <button type="button" className="desk-button" disabled={pdf.isPending} onClick={() => pdf.mutate()}>
        {pdf.isPending ? <><BoxArt size={16} mono />{t`Preparing PDF…`}</> : t`Download ticket PDF`}</button>
    </figcaption>
    {pdf.error ? <p role="alert" className="text-sm text-danger">{t`The ticket PDF could not be prepared. Try again.`}</p> : null}
  </figure>;
}
