// After a valid scan, staff may record the member as present in the space. The scan only
// identifies the person (Q-I10); the staff member is the one who checks them in.
import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { staffRequest, StructuredApiError } from "../../../../lib/api";

export function PresenceCheckIn({ makerspaceId, payload }: { makerspaceId: number; payload: string }) {
  const [minutes, setMinutes] = useState(120);
  const checkIn = useMutation({
    mutationFn: () => staffRequest<{ session_id: number }>(`/admin/makerspaces/${makerspaceId}/member-cards/presence-check-in`,
      { method: "POST", body: JSON.stringify({ payload, duration_minutes: minutes }) }),
  });
  if (checkIn.isSuccess) return <p role="status" className="text-sm text-success-ink">{t`Checked in for ${minutes / 60} hours.`}</p>;
  const error = checkIn.error instanceof StructuredApiError && checkIn.error.status === 404
    ? "Presence is off for this space, or this card can't be checked in." : checkIn.error instanceof Error ? checkIn.error.message : null;
  return <div className="flex flex-wrap items-end gap-2">
    <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Stay`}</span>
      <select className="desk-input min-h-11" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}>
        {[60, 120, 240, 480].map((value) => <option key={value} value={value}>{value / 60} hours</option>)}
      </select>
    </label>
    <button type="button" className="desk-button min-h-11" disabled={!payload || checkIn.isPending}
      onClick={() => checkIn.mutate()}>{checkIn.isPending ? t`Checking in…` : t`Check in at the space`}</button>
    {error ? <p role="alert" className="basis-full text-sm text-danger">{error}</p> : null}
  </div>;
}
