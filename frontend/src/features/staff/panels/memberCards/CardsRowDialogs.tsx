// The per-card dialogs of the Cards tab (reissue, revoke with a required note, photo
// request) and the row-menu actions that need no dialog (downloads, email).
import { useState } from "react";

import { ErrorBlock } from "../../../../components/ui";
import { toast } from "../../../../components/ui/toastStore";
import { useReissueCard, useRevokeCard } from "./api";
import { useDownloadCard, useEmailCard, useRequestPhoto } from "./apiCards";
import { PhotoRequestDialog, ReissueCardDialog, RevokeCardDialog } from "./CardDialogs";
import type { MemberCard, ReissueReason } from "./types";

const message = (error: unknown) => (error instanceof Error ? error.message : undefined);

export function useCardRowActions(makerspaceId: number, emailAvailable: boolean) {
  const [reissueTarget, setReissueTarget] = useState<MemberCard | null>(null);
  const [reissueReason, setReissueReason] = useState<ReissueReason>("lost");
  const [revokeTarget, setRevokeTarget] = useState<MemberCard | null>(null);
  const [revokeNote, setRevokeNote] = useState("");
  const [photoTarget, setPhotoTarget] = useState<MemberCard | null>(null);
  const [photoReason, setPhotoReason] = useState("");
  const reissue = useReissueCard(makerspaceId);
  const revoke = useRevokeCard(makerspaceId);
  const download = useDownloadCard();
  const email = useEmailCard();
  const photo = useRequestPhoto(makerspaceId);

  const rowActions = (card: MemberCard) => [
    { label: "Download PDF", onClick: () => download.mutate({ card, format: "pdf" }) },
    { label: "Download PNG", onClick: () => download.mutate({ card, format: "png" }) },
    ...(emailAvailable ? [{ label: "Email card", onClick: () => email.mutate(card, {
      onSuccess: () => toast(`Card emailed to ${card.printed_name}.`, { tone: "success" }),
      onError: (error) => toast(message(error) ?? "The card couldn't be emailed.", { tone: "error" }),
    }) }] : []),
    { label: "Request new photo", confirms: true, onClick: () => { setPhotoReason(""); setPhotoTarget(card); } },
  ];

  const dialogs = <>
    {download.error ? <ErrorBlock error={download.error} /> : null}
    <ReissueCardDialog card={reissueTarget} reason={reissueReason} pending={reissue.isPending} error={message(reissue.error)}
      onReasonChange={setReissueReason} onClose={() => setReissueTarget(null)}
      onSubmit={() => reissueTarget && reissue.mutate({ cardId: reissueTarget.id, reason: reissueReason },
        { onSuccess: () => setReissueTarget(null) })} />
    <RevokeCardDialog card={revokeTarget} note={revokeNote} pending={revoke.isPending} error={message(revoke.error)}
      onNoteChange={setRevokeNote} onClose={() => setRevokeTarget(null)}
      onSubmit={() => revokeTarget && revoke.mutate({ cardId: revokeTarget.id, note: revokeNote.trim() },
        { onSuccess: () => setRevokeTarget(null) })} />
    <PhotoRequestDialog card={photoTarget} reason={photoReason} pending={photo.isPending} error={message(photo.error)}
      onReasonChange={setPhotoReason} onClose={() => setPhotoTarget(null)}
      onSubmit={() => photoTarget && photo.mutate({ card: photoTarget, reason: photoReason.trim() },
        { onSuccess: () => { setPhotoTarget(null); toast("Photo update requested.", { tone: "success" }); } })} />
  </>;

  return {
    rowActions, dialogs,
    onReissue: (card: MemberCard) => { setReissueReason("lost"); setReissueTarget(card); },
    onRevoke: (card: MemberCard) => { setRevokeNote(""); setRevokeTarget(card); },
  };
}
