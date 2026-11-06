import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { ErrorBlock } from "../../components/ui";
import { SettingsEditorActions } from "./SettingsEditorActions";
import { SettingsRow } from "../../components/ui";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest, StructuredApiError } from "../../lib/api";
import { MakerspaceHoursEditor } from "./MakerspaceHoursEditor";
import { hoursDraft, serializeHours, validateHours, type MakerspaceProfile } from "./makerspaceProfileForm";

function countryLabel(code: string) {
  return new Intl.DisplayNames(["en"], { type: "region" }).of(code) ?? code;
}

export function MakerspaceProfileSettings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const currentId = useRef(makerspaceId);
  currentId.current = makerspaceId;
  const path = `/admin/makerspace/${makerspaceId}/profile`;
  const query = useQuery({ queryKey: ["makerspace-profile", makerspaceId], queryFn: () => staffRequest<MakerspaceProfile>(path) });
  const [draft, setDraft] = useState<MakerspaceProfile | null>(null);
  const [baseline, setBaseline] = useState<MakerspaceProfile | null>(null);
  const [hours, setHours] = useState(() => hoursDraft({}));
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saved, setSaved] = useState(false);
  useEffect(() => { setDraft(null); setBaseline(null); setDirty(false); setError(null); setSaved(false); }, [makerspaceId]);
  useEffect(() => {
    if (query.data && !dirty) { setDraft(query.data); setBaseline(query.data); setHours(hoursDraft(query.data.opening_hours)); }
  }, [query.data, dirty]);
  const mutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: object }) => staffRequest<MakerspaceProfile>(`/admin/makerspace/${id}/profile`, { method: "PATCH", body: JSON.stringify(body) }),
    onSuccess: (updated, { id }) => {
      client.setQueryData(["makerspace-profile", id], updated);
      if (currentId.current === id) { setDirty(false); setSaved(true); }
      for (const key of [["makerspace-settings", id], ["makerspaces"], ["staff", "makerspaces"], ["tenant-bootstrap"], ["payment-settings", id]]) {
        void client.invalidateQueries({ queryKey: key });
      }
    },
  });
  useEffect(() => { mutation.reset(); }, [makerspaceId, mutation.reset]);
  const changed = () => { setDirty(true); setSaved(false); setError(null); };
  return <SettingsQueryState query={query} resource="profile"><><div className="grid min-w-0 gap-4">


    {query.isPending ? <p role="status">{t`Loading profile…`}</p> : null}
    {query.error ? <ErrorBlock error={new Error(t`Couldn't load profile. Try again.`)} onRetry={() => { void query.refetch(); }} /> : null}
    {draft ? <form className="grid gap-4" onSubmit={event => {
      event.preventDefault();
      const invalid = validateHours(hours) ?? (!/^[a-z]{3}$/.test(draft.default_currency) ? "Enter a three-letter currency code." : null);
      setError(invalid);
      if (!invalid && dirty && !mutation.isPending) {
        const body: Record<string, unknown> = {};
        const openingHours = serializeHours(hours);
        if (JSON.stringify(openingHours) !== JSON.stringify(serializeHours(hoursDraft(baseline?.opening_hours ?? {})))) {
          body.opening_hours = openingHours;
        }
        for (const field of ["timezone", "country", "default_currency"] as const) {
          if (draft[field] !== baseline?.[field]) body[field] = draft[field];
        }
        mutation.mutate({ id: makerspaceId, body });
      }
    }}>
      <fieldset className="grid gap-4" disabled={mutation.isPending}>
        <legend className="sr-only">{t`Profile fields`}</legend>
        <SettingsRow label={t`Timezone`} htmlFor="profile-timezone" helper="Use local time for opening hours, reminders and bookings.">
          <select id="profile-timezone" className="desk-input max-w-full" value={draft.timezone} onChange={event => { changed(); setDraft({ ...draft, timezone: event.target.value }); }}>
            {draft.timezone_choices.map(zone => <option key={zone}>{zone}</option>)}
          </select>
        </SettingsRow>
        <SettingsRow label={t`Country`} htmlFor="profile-country" helper="Visible to staff only.">
          <select id="profile-country" className="desk-input max-w-full" value={draft.country} onChange={event => { changed(); setDraft({ ...draft, country: event.target.value }); }}>
            <option value="">{t`Unspecified`}</option>
            {draft.country_choices.map(code => <option key={code} value={code}>{countryLabel(code)}</option>)}
          </select>
        </SettingsRow>
        <SettingsRow label={t`Default currency`} htmlFor="profile-currency" helper="Used by payment settings. Existing charges keep their currency.">
          <input id="profile-currency" className="desk-input" maxLength={3} value={draft.default_currency} onChange={event => { changed(); setDraft({ ...draft, default_currency: event.target.value.toLowerCase() }); }} />
        </SettingsRow>
        <SettingsRow label={t`Opening hours`} helper="Set weekly hours and dated exceptions in the makerspace timezone.">
          <MakerspaceHoursEditor value={hours} onChange={value => { changed(); setHours(value); }} />
        </SettingsRow>
      </fieldset>
      {error ? <p role="alert" className="text-danger">{error}</p> : null}
      {mutation.error ? <p role="alert" className="text-danger">{mutation.error.message}{mutation.error instanceof StructuredApiError && mutation.error.body.fields && typeof mutation.error.body.fields === "object" ? ` ${Object.entries(mutation.error.body.fields).map(([field, messages]) => `${field}: ${messages}`).join("; ")}` : ""}</p> : null}
      {saved ? <p role="status">{t`Saved.`}</p> : null}
      <SettingsEditorActions dirty={dirty} onDiscard={() => { setDraft(baseline); setHours(hoursDraft(baseline?.opening_hours ?? {})); setDirty(false); setError(null); setSaved(false); }} pending={mutation.isPending} disabled={!dirty || mutation.isPending} />
    </form> : null}
  </div></></SettingsQueryState>;
}
