import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, Field, ListRow } from "../../../components/ui";
import { StructuredApiError } from "../../../lib/api";
import { lifecycleApi, lifecycleKeys } from "../membershipLifecycleApi";
import { Panel } from "../panels/shared";

/** Brand accent presets only; titles never take tenant hex colours. */
export const TITLE_COLOURS: [string, string][] = [
  ["", "Neutral"], ["maker_teal", "Maker Teal"], ["workshop_orange", "Workshop Orange"], ["citron", "Citron"],
  ["sky_blue", "Sky Blue"], ["warm_yellow", "Warm Yellow"],
];
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`That did not work.`);

/** X16: display-only member titles. They grant nothing; roles stay the only permissions. */
export function TitlesManager({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const titles = useQuery({ queryKey: lifecycleKeys.titles(makerspaceId), queryFn: () => lifecycleApi.titles(makerspaceId) });
  const [name, setName] = useState("");
  const [colour, setColour] = useState("");
  const refresh = () => client.invalidateQueries({ queryKey: lifecycleKeys.titles(makerspaceId) });
  const create = useMutation({ mutationFn: () => lifecycleApi.createTitle(makerspaceId, { name: name.trim(), colour }),
    onSuccess: () => { setName(""); void refresh(); } });
  const archive = useMutation({ mutationFn: (id: number) => lifecycleApi.archiveTitle(id), onSuccess: () => { void refresh(); } });
  const live = (titles.data ?? []).filter((title) => !title.archived_at);
  const failure = create.error ?? archive.error;
  return <Panel title={t`Member titles`}>
    <p className="mb-3 text-sm text-muted">{t`Titles such as “Treasurer” show on the register and the card. They are display only and grant no permissions.`}</p>
    {titles.isSuccess && !live.length ? <EmptyState message={t`No titles yet.`} /> : null}
    {live.map((title) => <ListRow key={title.id} title={title.name} identity={{ kind: "icon", icon: "User", tone: "accent" }}
      meta={TITLE_COLOURS.find(([key]) => key === title.colour)?.[1] ?? "Neutral"}
      right={<button className="desk-button" type="button" disabled={archive.isPending} onClick={() => archive.mutate(title.id)}>{t`Archive`}</button>} />)}
    <form className="mt-4 grid gap-2 sm:grid-cols-3" aria-label={t`New member title`}
      onSubmit={(event) => { event.preventDefault(); if (name.trim()) create.mutate(); }}>
      <Field label={t`Title`}><input className="desk-input" maxLength={60} value={name} onChange={(event) => setName(event.target.value)} /></Field>
      <Field label={t`Colour`}><select className="desk-input max-w-full" value={colour} onChange={(event) => setColour(event.target.value)}>
        {TITLE_COLOURS.map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
      <div className="flex items-end"><button className="desk-button-primary" type="submit" disabled={create.isPending || !name.trim()}>{t`Add title`}</button></div>
    </form>
    {failure ? <p role="alert" className="mt-2 text-sm text-danger">{errorText(failure)}</p> : null}
  </Panel>;
}
