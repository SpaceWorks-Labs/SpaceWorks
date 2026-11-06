// The event level of the design-approval switch (#136). Event cards and tickets publish with no
// approval by default (#128); an event, its organisation or the space may turn approval on.
import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorBlock } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { ApprovalLevelSelect, type ApprovalValue } from "../../cards/ApprovalLevelSelect";

type EventCardSettings = { extras_visible_to_organizers: boolean; design_approval_required: ApprovalValue;
  design_approval_inherited: boolean };

export function EventCardApproval({ eventId }: { eventId: number }) {
  const client = useQueryClient();
  const key = ["event-card-settings", eventId];
  const path = `/admin/events/${eventId}/card-settings`;
  const settings = useQuery({ queryKey: key, queryFn: () => staffRequest<EventCardSettings>(path) });
  const save = useMutation({
    mutationFn: (value: ApprovalValue) => staffRequest<EventCardSettings>(path, { method: "PUT",
      body: JSON.stringify({ design_approval_required: value }) }),
    onSuccess: (saved) => {
      client.setQueryData(key, saved);
      void client.invalidateQueries({ queryKey: ["card-design"] });
      void client.invalidateQueries({ queryKey: ["event-card-designs", eventId] });
    },
  });
  if (!settings.data) return settings.error ? <ErrorBlock error={settings.error} resource="card settings" /> : null;
  return <div className="grid max-w-md gap-1">
    <ApprovalLevelSelect label={t`Design changes for this event`} value={settings.data.design_approval_required}
      inherited={settings.data.design_approval_inherited} inheritLabel="Follow the organisation and space"
      disabled={save.isPending} onChange={(value) => save.mutate(value)} />
    {save.error ? <ErrorBlock error={save.error} /> : null}
  </div>;
}
