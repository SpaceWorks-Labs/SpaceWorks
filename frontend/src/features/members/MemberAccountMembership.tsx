import { DangerZone, StatusPill } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accountKey, endMembership, ownMembership } from "./memberAccountApi";

export function MemberAccountMembership({ makerspaceId, onLeft }: { makerspaceId: number; onLeft: () => void }) {
  const [action, setAction] = useState<"cancel" | "leave" | null>(null);
  const [reason, setReason] = useState("");
  const client = useQueryClient();
  const membership = useQuery({ queryKey: [...accountKey(makerspaceId), "membership"], queryFn: () => ownMembership(makerspaceId), retry: false });
  const change = useMutation({ mutationFn: () => endMembership(makerspaceId, action!, reason), onSuccess: () => {
    void client.invalidateQueries({ queryKey: ["member"] });
    if (action === "leave") onLeft();
    setAction(null); setReason("");
  } });
  // Rendered inside the account page's Membership settings section, which owns the card and the heading.
  return <div className="grid min-w-0 gap-3">
    {membership.isLoading ? <p role="status" className="text-sm text-muted">Loading membership…</p> : null}
    {membership.data?.renewal_cancelled_at ? <p role="status" className="text-sm text-ink">Renewal is cancelled. Your current term remains available until it ends.</p> : null}
    <p className="text-sm text-muted">Cancel renewal to keep your current term. Leaving ends your membership immediately. Existing loans and payment records remain on file.</p>
    {membership.data ? <><div><StatusPill label={membership.data.status || "Membership"} /></div><DangerZone title="Cancel renewal" consequence="Your current term stays available until it ends." action={{ label: "Cancel renewal", disabled: Boolean(membership.data.renewal_cancelled_at) || change.isPending, disabledReason: membership.data.renewal_cancelled_at ? "Renewal is already cancelled" : change.isPending ? "Updating membership" : undefined, onClick: () => { change.reset(); setAction("cancel"); } }} /><DangerZone title="Leave makerspace" consequence="Membership ends immediately. Existing loans and payment records remain on file." action={{ label: "Leave makerspace", disabled: change.isPending, disabledReason: change.isPending ? "Updating membership" : undefined, onClick: () => { change.reset(); setAction("leave"); } }} /></> : null}
    {action ? <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); change.mutate(); }}>
      <label className="grid gap-2 text-sm font-semibold">Reason<textarea className="desk-input w-full" required maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} /></label>
      <p className="text-sm text-ink">{action === "leave" ? "Confirm that you want to leave this makerspace now." : "Confirm that you want to stop future renewal."}</p>
      <div className="flex flex-wrap gap-2 [&>button]:flex-1 sm:[&>button]:flex-none"><button type="submit" className="desk-button-primary" disabled={!reason.trim() || change.isPending}>Confirm {action === "leave" ? "leave" : "cancellation"}</button><button type="button" className="desk-button" disabled={change.isPending} onClick={() => setAction(null)}>Keep membership</button></div>
    </form> : null}
    {membership.error || change.error ? <p role="alert" className="text-sm text-danger">{(membership.error || change.error)?.message}</p> : null}
  </div>;
}
