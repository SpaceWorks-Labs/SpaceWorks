import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { StructuredApiError } from "../../../lib/api";
import { usePrintReceipts } from "../../../components/card-print";
import { Modal } from "../../../components/ui";
import { deskKey, fetchDesk, sendDeskReceipts } from "../eventBadges/deskBadgeApi";
import { DeskPrintSheet } from "../eventBadges/DeskPrintSheet";
import { sessionScope } from "../eventProgramme/sessionScope";
import { LegacyQuickBadgePrint } from "./LegacyQuickBadgePrint";

/**
 * Shown after an online check-in. With `events.badge_desk_print` on it previews and prints the person's real
 * badge in the browser (the desk route answers 404 when the switch is off, which falls back to the older
 * server-PDF flow). The print receipt is sent at once; it is never a reason to hold up the next guest.
 */
export function QuickBadgePrint({ eventId, registrationId, name, onClose }: {
  eventId: number; registrationId: number; name: string; onClose: () => void;
}) {
  const [, setParams] = useSearchParams();
  const desk = useQuery({ queryKey: [...deskKey(eventId, registrationId), ...sessionScope()], retry: false, gcTime: 0, staleTime: 0,
    queryFn: () => fetchDesk(eventId, registrationId) });
  const receipts = usePrintReceipts<{ registration_id: number; method: "desk"; stock?: string; role?: string }>({
    send: (receipt) => sendDeskReceipts(eventId, [receipt]) });
  if (desk.isPending) return null;
  if (desk.error instanceof StructuredApiError && desk.error.status === 404) {
    return <LegacyQuickBadgePrint eventId={eventId} registrationId={registrationId} name={name} onClose={onClose} />;
  }
  const badge = desk.data?.badge;
  if (!badge || !desk.data) {
    return <Modal open onClose={onClose} title={t`Print a badge?`} footer={<button className="desk-button" type="button" onClick={onClose}>{t`Done`}</button>}>
      <p role="alert" className="text-sm text-danger">{desk.error?.message ?? t`This badge could not be loaded.`}</p></Modal>;
  }
  return <DeskPrintSheet badge={badge} bundle={desk.data} onSkip={onClose}
    onEdit={() => { onClose(); setParams((previous) => { const next = new URLSearchParams(previous); next.set("eventTab", "certificates"); return next; }); }}
    onPrinted={(info) => receipts.record({ registration_id: badge.registration_id, method: "desk", ...info })} />;
}
