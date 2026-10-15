import { toast, invalidateToastUndo } from "../../components/ui/toastStore";
import { ActionControl } from "../../components/ui";
import { SettingsRow } from "../../components/ui";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { StatusPill as Badge } from "../../components/ui";
import type { Makerspace as MakerspaceContract, MembershipPolicyEnum } from "../../generated/api";
import { staffRequest } from "../../lib/api";
import type { Makerspace } from "./StaffPanels";
import { MembershipAdmissionSettings } from "./MembershipAdmissionSettings";

export function MakerspaceMembershipSettings({ makerspace, settings, loading }: {
  makerspace: Makerspace;
  settings?: Makerspace;
  loading: boolean;
}) {
  const queryClient = useQueryClient();
  const duesForm = useRef<HTMLFormElement>(null);
  const admissionEnabled = (settings?.enabled_modules ?? makerspace.enabled_modules ?? []).includes("membership");
  const membershipPolicy = settings?.membership_policy ?? makerspace.membership_policy ?? "request";
  const referralsEnabled = settings?.referrals_enabled ?? makerspace.referrals_enabled ?? false;
  const [duesAmount, setDuesAmount] = useState(
    settings?.membership_dues_amount ?? makerspace.membership_dues_amount ?? "0.00",
  );
  useEffect(() => {
    setDuesAmount(settings?.membership_dues_amount ?? makerspace.membership_dues_amount ?? "0.00");
  }, [settings?.membership_dues_amount, makerspace.membership_dues_amount]);
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["makerspace-settings", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["makerspaces"] });
    queryClient.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
  };
  const updateMembershipPolicy = useMutation({
    mutationFn: (next: MembershipPolicyEnum) => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ membership_policy: next }),
    }),
    onSuccess: refresh,
  });
  const updateReferrals = useMutation({
    mutationFn: (next: boolean) => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ referrals_enabled: next }),
    }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updateReferrals`),
    onSuccess: async (_data, next) => {
      await (refresh)();
      toast(`Member referrals turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updateReferrals`, undo: async () => {
        await ((next: boolean) => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ referrals_enabled: next }),
    }))(!next);
        await (refresh)();
      } });
    },
  });
  const lapsedCannotBorrow = settings?.lapsed_members_cannot_borrow;
  const updateLapsed = useMutation({
    mutationFn: (next: boolean) => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ lapsed_members_cannot_borrow: next }),
    }),
    onMutate: () => invalidateToastUndo(`settings-${makerspace.id}-updateLapsed`),
    onSuccess: async (_data, next) => {
      await (refresh)();
      toast(`Lapsed borrowing restriction turned ${next ? "on" : "off"}.`, { undoKey: `settings-${makerspace.id}-updateLapsed`, undo: async () => {
        await ((next: boolean) => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ lapsed_members_cannot_borrow: next }),
    }))(!next);
        await (refresh)();
      } });
    },
  });
  const updateDues = useMutation({
    mutationFn: () => staffRequest<MakerspaceContract>(`/admin/makerspaces/${makerspace.id}`, {
      method: "PATCH", body: JSON.stringify({ membership_dues_amount: duesAmount }),
    }),
    onSuccess: refresh,
  });

  return <>
    {admissionEnabled ? <MembershipAdmissionSettings makerspaceId={makerspace.id} /> : <SettingsRow label="Membership joining" helper="Choose whether people join immediately, request approval, or need an invitation. This only controls self-join; manager invitations remain available."><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-3  md:items-start">
        <div className="grid min-w-0 max-w-2xl gap-2">
          <div className="flex flex-wrap items-center gap-2"><Badge label="" tone={membershipPolicy === "invite_only" ? "neutral" : "success"}>{membershipPolicyLabel(membershipPolicy)}</Badge></div>

          {updateMembershipPolicy.error ? <p className="text-sm text-danger" role="alert">{updateMembershipPolicy.error.message}</p> : null}
        </div>
        <select aria-label="Membership joining policy" className="desk-input w-full" value={membershipPolicy} disabled={loading || updateMembershipPolicy.isPending} onChange={(event) => updateMembershipPolicy.mutate(event.target.value as MembershipPolicyEnum)}>
          <option value="open">Join instantly</option><option value="request">Request approval</option><option value="invite_only">Invite-only</option>
        </select>
      </div>
    </div></SettingsRow>}
    <SettingsRow label="Member referrals" helper="Allow eligible active members to invite someone. Individual referral permission is managed in the member roster."><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-3  md:items-start">
        <div className="grid min-w-0 max-w-2xl gap-2">
          <div className="flex flex-wrap items-center gap-2"><Badge label="" tone={referralsEnabled ? "success" : "neutral"}>{referralsEnabled ? "On" : "Off"}</Badge></div>

          {updateReferrals.error ? <p className="text-sm text-danger" role="alert">{updateReferrals.error.message}</p> : null}
        </div>
        <label className="min-h-11 flex min-w-0 items-start gap-3 text-sm text-ink sm:justify-self-start md:justify-self-end"><input className="mt-1 h-4 w-4" type="checkbox" checked={referralsEnabled} disabled={loading || updateReferrals.isPending} onChange={(event) => updateReferrals.mutate(event.target.checked)} /><span className="font-semibold">Enable referrals</span></label>
      </div>
    </div></SettingsRow>
    {lapsedCannotBorrow !== undefined ? <SettingsRow label="Lapsed members" helper="When on, a member whose plan term has expired or was cancelled cannot submit borrow requests until a new term is started."><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-3  md:items-start">
        <div className="grid min-w-0 max-w-2xl gap-2">
          <div className="flex flex-wrap items-center gap-2"><Badge label="" tone={lapsedCannotBorrow ? "warn" : "neutral"}>{lapsedCannotBorrow ? "Cannot borrow" : "Can borrow"}</Badge></div>

          {updateLapsed.error ? <p className="text-sm text-danger" role="alert">{updateLapsed.error.message}</p> : null}
        </div>
        <label className="min-h-11 flex min-w-0 items-start gap-3 text-sm text-ink sm:justify-self-start md:justify-self-end"><input className="mt-1 h-4 w-4" type="checkbox" checked={lapsedCannotBorrow} disabled={loading || updateLapsed.isPending} onChange={(event) => updateLapsed.mutate(event.target.checked)} /><span className="font-semibold">Lapsed members cannot borrow</span></label>
      </div>
    </div></SettingsRow> : null}
    <SettingsRow label="Membership dues" helper="Set the amount charged when a membership is activated. Use 0 for no charge."><div className="@container grid min-w-0 gap-4">
      <div className="grid min-w-0 gap-3  md:items-start">
        <div className="grid min-w-0 max-w-2xl gap-2">


          {updateDues.error ? <p className="text-sm text-danger" role="alert">{updateDues.error.message}</p> : null}
        </div>
        <form ref={duesForm} className="grid gap-2" onSubmit={(event) => { event.preventDefault(); updateDues.mutate(); }}>
          <label className="grid gap-1 text-sm font-semibold text-ink">Dues amount
            <input className="desk-input" type="number" min="0" step="0.01" value={duesAmount} disabled={loading || updateDues.isPending} onChange={(event) => setDuesAmount(event.target.value)} />
          </label>
          {duesAmount !== (settings?.membership_dues_amount ?? makerspace.membership_dues_amount ?? "0.00") || updateDues.isPending ? <div className="sticky bottom-0 z-10 flex flex-wrap justify-end gap-2 border-t border-line bg-panel p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <ActionControl action={{ label: "Discard", disabled: updateDues.isPending, disabledReason: updateDues.isPending ? "Wait for the dues update." : undefined,
              onClick: () => setDuesAmount(settings?.membership_dues_amount ?? makerspace.membership_dues_amount ?? "0.00") }} />
            <ActionControl primary action={{ label: "Save dues", pending: updateDues.isPending, pendingLabel: "Saving…", disabled: loading,
              disabledReason: loading ? "Wait for settings to load." : undefined, onClick: () => duesForm.current?.requestSubmit() }} />
          </div> : null}
        </form>
      </div>
    </div></SettingsRow>
  </>;
}

function membershipPolicyLabel(policy: MembershipPolicyEnum) {
  return { open: "Join instantly", request: "Request approval", invite_only: "Invite-only" }[policy];
}
