import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Field, SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { useStaffGet } from "./panels/shared";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsQueryState } from "./SettingsQueryState";

export type ReservationPolicy = { pickup_window_hours: number; reservation_max_days_ahead: number; waitlist_offer_hours: number };

const FIELDS = [
  ["pickup_window_hours", "Hours to collect an accepted request", "0 = accepted requests never expire."],
  ["reservation_max_days_ahead", "How far ahead members may book a collection (days)", undefined],
  ["waitlist_offer_hours", "Hours a waitlist offer is held", "After this the items go to the next person waiting."],
] as const;

export const reservationPolicyKey = (makerspaceId: number) => ["staff", "loan-reservation-policy", makerspaceId];

/** Pickup deadlines, how far ahead a collection can be booked, and how long a waitlist offer is held. */
export function LoanReservationPolicySettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const path = `/admin/makerspace/${makerspaceId}/loan-reservation-policy`;
  const query = useStaffGet<ReservationPolicy>(reservationPolicyKey(makerspaceId), path);
  const [form, setForm] = useState<ReservationPolicy | null>(null);
  useEffect(() => { if (query.data) setForm(query.data); }, [query.data]);
  const save = useMutation({
    mutationFn: (value: ReservationPolicy) => staffRequest<ReservationPolicy>(path, { method: "PUT", body: JSON.stringify(value) }),
    onSuccess: data => { client.setQueryData(reservationPolicyKey(makerspaceId), data); setForm(data); },
  });
  const dirty = Boolean(form && query.data && JSON.stringify(form) !== JSON.stringify(query.data));
  return <SettingsQueryState query={query} resource={t`pickup and waitlist timing`}>{form ? <SettingsRow label={t`Pickup and waitlist timing`}
    helper={t`Applies when Pickup windows, Loan reservations or the Loan waitlist are switched on in Features.`}>
    <form className="@container grid gap-3 rounded-md border border-line p-4" onSubmit={event => { event.preventDefault(); save.mutate(form); }}>
      <div className="grid gap-3 @md:grid-cols-3">
        {FIELDS.map(([field, label, hint]) => <Field key={field} label={label} hint={hint}>
          <input className="desk-input" type="number" required min={0} step={1} value={form[field]} disabled={save.isPending}
            onChange={event => setForm({ ...form, [field]: Number(event.target.value) })} />
        </Field>)}
      </div>
      <div><SettingsEditorActions dirty={dirty} onDiscard={() => setForm(query.data ?? null)} pending={save.isPending} disabled={save.isPending} /></div>
      {save.error ? <p className="text-sm text-danger" role="alert">{save.error.message}</p> : null}
      {save.isSuccess && !dirty ? <p className="text-sm text-muted" role="status">{t`Pickup and waitlist timing saved.`}</p> : null}
    </form></SettingsRow> : null}</SettingsQueryState>;
}
