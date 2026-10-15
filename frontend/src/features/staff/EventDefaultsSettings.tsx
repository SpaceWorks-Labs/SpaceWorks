import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";

type Audience = "members" | "accounts" | "invite" | "participating_organizations";
type Settings = { event_default_registration_audience: Audience; enabled_features: string[] };

export function EventDefaultsSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
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
  return <form className="grid gap-3 rounded-md border border-line p-4" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
    <h3 className="title-section">Event defaults</h3>
    <p className="text-sm text-muted">New events and recurring series start with this audience. Existing events keep their audience. Ticket currency uses the default in Location &amp; hours.</p>
    <label className="grid gap-1 text-sm">Default registration audience
      <select className="desk-input" value={audience} disabled={!query.data || save.isPending} onChange={(event) => { setDraft(event.target.value as Audience); save.reset(); }}>
        <option value="members">Members</option><option value="accounts">Authenticated accounts</option><option value="invite">Invited accounts</option>
        {organizationAudienceEnabled || audience === "participating_organizations" ? <option value="participating_organizations" disabled={!organizationAudienceEnabled}>Participating organizations</option> : null}
      </select>
    </label>
    {audienceDisabled ? <p className="text-sm text-muted">Enable Participating organizations audience in Features to use this default, or choose another audience.</p> : null}
    {query.error || save.error ? <p role="alert" className="text-danger">{(save.error ?? query.error)?.message}</p> : null}
    <button className="desk-button-primary w-fit" disabled={!draft || save.isPending || audienceDisabled}>Save event defaults</button>
    {save.isSuccess ? <p role="status">Event defaults saved.</p> : null}
  </form>;
}
