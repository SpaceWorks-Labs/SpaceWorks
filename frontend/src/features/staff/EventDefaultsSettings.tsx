import { t } from "@lingui/core/macro";
import { useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SettingsRow } from "../../components/ui";
import { AudienceOptions } from "./EventAudienceOptions";
import { staffRequest } from "../../lib/api";

type Audience = "members" | "accounts" | "invite" | "participating_organizations";
type Settings = { event_default_registration_audience: Audience; enabled_features: string[] };

export function EventDefaultsSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const selectId = useId();
  const path = `/admin/makerspaces/${makerspaceId}`;
  const key = ["makerspace-settings", makerspaceId];
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<Settings>(path) });
  const [draft, setDraft] = useState<Audience | null>(null);
  const audience = draft ?? query.data?.event_default_registration_audience ?? "members";
  const organizationAudienceEnabled = query.data?.enabled_features.includes("events.organization_audience") ?? false;
  const audienceDisabled = audience === "participating_organizations" && !organizationAudienceEnabled;
  const save = useMutation({
    mutationFn: () => staffRequest<Settings>(path, { method: "PATCH", body: JSON.stringify({ event_default_registration_audience: draft }) }),
    onSuccess: (data) => {
      client.setQueryData(key, data); setDraft(null);
      void client.invalidateQueries({ queryKey: ["staff", "makerspaces"] });
      void client.invalidateQueries({ queryKey: ["events", makerspaceId] });
    },
  });
  return <SettingsRow label={t`Default registration audience`} htmlFor={selectId}
    helper="New events and recurring series start with this audience. Existing events keep their audience. Ticket currency uses the default in Location & hours.">
    <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <select id={selectId} className="desk-input w-full min-w-0" value={audience} disabled={!query.data || save.isPending} onChange={(event) => { setDraft(event.target.value as Audience); save.reset(); }}>
        <AudienceOptions value={audience} organizationAudienceEnabled={organizationAudienceEnabled} />
      </select>
      {audienceDisabled ? <p className="text-sm text-muted">{t`Enable the Participating organizations audience in Features to use Selected organizations as the default, or choose another audience.`}</p> : null}
      {query.error || save.error ? <p role="alert" className="text-sm text-danger">{(save.error ?? query.error)?.message}</p> : null}
      <button className="desk-button-primary justify-self-start" type="submit" disabled={!draft || save.isPending || audienceDisabled}>{t`Save event defaults`}</button>
      {save.isSuccess ? <p role="status" className="text-sm text-muted">{t`Event defaults saved.`}</p> : null}
    </form>
  </SettingsRow>;
}
