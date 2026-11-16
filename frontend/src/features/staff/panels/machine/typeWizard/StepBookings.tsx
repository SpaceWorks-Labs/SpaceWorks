import { plural, t } from "@lingui/core/macro";
import { useState } from "react";

import { BoxArt } from "../../../../../components/BoxSpinner";
import { LogoLoader } from "../../../../../components/LogoLoader";
import { ConfirmDialog } from "../../../../../components/ui";
import { useApplyBookingDefaults, useSaveTypeSetup, useTypeSetup, type ApprovalMode, type TypeSetup } from "./typeSetupApi";
import type { StepProps } from "./wizardTypes";

type Form = { slot: string; before: string; after: string; mode: ApprovalMode };

/** A whole number in range as text, or "" when blank; `null` for a value the server would refuse. */
const whole = (text: string, min: number): number | null | "" => {
  if (text.trim() === "") return "";
  const value = Number(text);
  return Number.isInteger(value) && value >= min && value <= 1440 ? value : null;
};
const num = (value: number | null | undefined) => value === null || value === undefined ? "" : String(value);
const noDefaults = (setup: TypeSetup) => setup.booking_slot_minutes === null && setup.booking_buffer_before_minutes === null
  && setup.booking_buffer_after_minutes === null && !setup.booking_approval_mode;

function BookingsForm({ ctx, setup }: StepProps & { setup: TypeSetup }) {
  const typeId = ctx.machineType!.id;
  const suggested = ctx.prefill?.bookings ?? ctx.spec?.bookings;
  const fresh = noDefaults(setup);
  const saved: Form = fresh
    ? { slot: num(suggested?.slot_minutes), before: num(suggested?.buffer_minutes), after: num(suggested?.buffer_minutes),
      mode: suggested?.requires_approval === undefined ? "" : suggested.requires_approval ? "approve" : "instant" }
    : { slot: num(setup.booking_slot_minutes), before: num(setup.booking_buffer_before_minutes), after: num(setup.booking_buffer_after_minutes), mode: setup.booking_approval_mode };
  const [draft, setDraft] = useState<Form | null>(null);
  const [confirming, setConfirming] = useState(false);
  const form = draft ?? saved;
  const save = useSaveTypeSetup(ctx.makerspaceId, typeId);
  const apply = useApplyBookingDefaults(ctx.makerspaceId, typeId);
  const slot = whole(form.slot, 1); const before = whole(form.before, 0); const after = whole(form.after, 0);
  const invalid = slot === null || before === null || after === null;
  const dirty = draft !== null || fresh && (saved.slot !== "" || saved.before !== "" || saved.mode !== "");
  const set = (patch: Partial<Form>) => { save.reset(); apply.reset(); setDraft({ ...form, ...patch }); };
  const field = (label: string, key: "slot" | "before" | "after", hint: string, bad: boolean) => <label className="grid gap-1 text-sm">{label}
    <input className="desk-input tabular-nums" inputMode="numeric" value={form[key]} placeholder={t`No default`} onChange={event => set({ [key]: event.target.value })} />
    {bad ? <span className="text-xs text-danger">{hint}</span> : null}</label>;
  return <form className="grid gap-3" onSubmit={event => { event.preventDefault(); if (invalid) return;
    save.mutate({ booking_slot_minutes: slot === "" ? null : slot, booking_buffer_before_minutes: before === "" ? null : before,
      booking_buffer_after_minutes: after === "" ? null : after, booking_approval_mode: form.mode }, { onSuccess: () => setDraft(null) }); }}>
    <p className="text-sm text-muted">{t`A new bookable space for this machine type, or for one of its machines, starts with these values. Leave a value empty for no default.`}</p>
    {fresh && suggested && (saved.slot !== "" || saved.before !== "" || saved.mode !== "") ? <p className="text-sm text-muted">{t`These are the template's suggestions. Save to keep them.`}</p> : null}
    <div className="grid gap-3 sm:grid-cols-3">
      {field(t`Slot length (minutes)`, "slot", t`Use a whole number from 1 to 1440.`, slot === null)}
      {field(t`Buffer before (minutes)`, "before", t`Use a whole number from 0 to 1440.`, before === null)}
      {field(t`Buffer after (minutes)`, "after", t`Use a whole number from 0 to 1440.`, after === null)}
    </div>
    <label className="grid gap-1 text-sm sm:max-w-xs">{t`Who approves a booking`}
      <select className="desk-input" value={form.mode} onChange={event => set({ mode: event.target.value as ApprovalMode })}>
        <option value="">{t`No default`}</option><option value="instant">{t`Confirmed straight away`}</option><option value="approve">{t`Staff approve each booking`}</option></select></label>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    {save.isSuccess && !dirty ? <p role="status" className="text-sm text-success-ink">{t`Booking defaults saved.`}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="submit" className="desk-button-primary min-h-11" disabled={invalid || save.isPending || !dirty}>
        {save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save booking defaults`}</button>
      <button type="button" className="desk-button min-h-11" disabled={dirty || fresh || apply.isPending} onClick={() => { apply.reset(); setConfirming(true); }}>{t`Apply to existing spaces`}</button></div>
    {dirty ? <p className="text-xs text-muted">{t`Save before applying to existing spaces.`}</p> : null}
    {apply.isSuccess ? <p role="status" className="text-sm text-success-ink">{apply.data.spaces.length
      ? plural(apply.data.spaces.length, { one: "Updated # existing bookable space.", other: "Updated # existing bookable spaces." }) : t`This type has no bookable spaces to update.`}</p> : null}
    {apply.error ? <p role="alert" className="text-sm text-danger">{apply.error.message}</p> : null}
    <ConfirmDialog open={confirming} title={t`Apply to existing spaces?`} confirmLabel={t`Apply`} pending={apply.isPending}
      message={t`This overwrites the slot length, buffers and approval rule of every bookable space of this machine type that already exists. You need booking authority to do this.`}
      onCancel={() => setConfirming(false)} onConfirm={() => apply.mutate(undefined, { onSettled: () => setConfirming(false) })} />
  </form>;
}

/** Step 7: booking defaults new bookable spaces of this type start with, and a one-time apply to the existing ones. */
export function StepBookings({ ctx }: StepProps) {
  const setup = useTypeSetup(ctx.makerspaceId, ctx.machineType!.id);
  if (setup.isLoading) return <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" />;
  if (setup.isError) return <p role="alert" className="text-sm text-danger">{setup.error.message}</p>;
  return <BookingsForm key={setup.data?.updated_at ?? "new"} ctx={ctx} setup={setup.data!} />;
}
