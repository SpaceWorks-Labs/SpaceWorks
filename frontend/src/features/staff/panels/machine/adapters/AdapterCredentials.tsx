import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import { Field, RelativeTime, StatusPill } from "../../../../../components/ui";
import { adapterErrorMessage } from "./adapterCopy";
import { adapterKeys, adaptersApi, type Credential } from "./adaptersApi";
import { BoxArt } from "../../../../../components/BoxSpinner";

type Member = { id: number; user: { id: number; display_name: string; username: string } };

/** `user` is the member's account id (`CredentialSerializer`); names come from the member list, falling back to the id. */
export const credentialPerson = (user: unknown, names: Map<number, string>): string =>
  typeof user === "number" ? names.get(user) ?? t`Member #${user}` : t`Unknown member`;

function AddCredential({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [query, setQuery] = useState("");
  const [person, setPerson] = useState<Member["user"] | null>(null);
  const [kind, setKind] = useState<"nfc" | "pin">("nfc");
  const [secret, setSecret] = useState("");
  const [label, setLabel] = useState("");
  const search = query.trim();
  const members = useQuery({ queryKey: ["device-adapters", makerspaceId, "member-search", search], enabled: search.length >= 2 && person === null,
    queryFn: () => staffRequest<{ results: Member[] }>(`/admin/memberships?${new URLSearchParams({ makerspace_id: String(makerspaceId), status: "active", q: search })}`) });
  const add = useMutation({ mutationFn: () => adaptersApi.addCredential(makerspaceId, { user_id: person!.id, kind, secret, ...(label.trim() ? { label: label.trim() } : {}) }),
    onSuccess: () => { setSecret(""); setLabel(""); setPerson(null); setQuery(""); void client.invalidateQueries({ queryKey: adapterKeys.credentials(makerspaceId) }); } });
  const pinBad = kind === "pin" && secret !== "" && !/^\d{6,12}$/.test(secret);
  const ready = person !== null && secret.length >= 4 && !pinBad;
  return <form className="grid gap-4 rounded-2xl border border-line bg-panel p-4" aria-label={t`Add a credential`}
    onSubmit={event => { event.preventDefault(); if (ready) add.mutate(); }}>
    <h3 className="title-section">{t`Add a credential`}</h3>
    <Field label={t`Member`} hint={person ? undefined : t`Type at least two letters of a name or username.`}>
      {person ? <div className="flex items-center gap-2"><span className="desk-input flex-1">{person.display_name || person.username}</span>
        <button type="button" className="desk-button" onClick={() => setPerson(null)}>{t`Change`}</button></div>
        : <input className="desk-input" type="search" value={query} onChange={event => setQuery(event.target.value)} />}
    </Field>
    {!person && (members.data?.results ?? []).length ? <ul className="grid gap-1" aria-label={t`Matching members`}>{members.data!.results.slice(0, 6).map(row => <li key={row.id}>
      <button type="button" className="desk-button w-full justify-start" onClick={() => setPerson(row.user)}>{row.user.display_name || row.user.username} <span className="text-muted">@{row.user.username}</span></button></li>)}</ul> : null}
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label={t`Kind`}><select className="desk-input" value={kind} onChange={event => { setKind(event.target.value as "nfc" | "pin"); setSecret(""); }}>
        <option value="nfc">{t`NFC tag`}</option><option value="pin">{t`PIN`}</option></select></Field>
      <Field label={kind === "pin" ? t`PIN` : t`Tag id`} hint={kind === "pin" ? t`6 to 12 digits. Space Works keeps a one-way digest and can never show it again, so tell the member their PIN now.` : t`Scan or type the tag id. It is stored as a one-way digest and cannot be shown again.`}
        error={pinBad ? t`A PIN is 6 to 12 digits.` : undefined}>
        <input className="desk-input" type="password" autoComplete="off" maxLength={64} inputMode={kind === "pin" ? "numeric" : "text"} value={secret} onChange={event => setSecret(event.target.value)} /></Field>
    </div>
    <Field label={t`Label (optional)`} hint={t`For example: Blue keyring tag.`}><input className="desk-input" maxLength={80} value={label} onChange={event => setLabel(event.target.value)} /></Field>
    <p className="text-sm text-muted">{kind === "pin" ? t`Adding a PIN replaces this member's current PIN.` : t`Adding a tag replaces this member's current NFC tag.`}</p>
    {add.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(add.error)}</p> : null}
    <button type="submit" className="desk-button-primary justify-self-start" disabled={!ready || add.isPending}>{add.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Add credential`}</button>
  </form>;
}

function CredentialRow({ row, makerspaceId, names }: { row: Credential; makerspaceId: number; names: Map<number, string> }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const disable = useMutation({ mutationFn: () => adaptersApi.disableCredential(row.id),
    onSuccess: () => { setConfirming(false); void client.invalidateQueries({ queryKey: adapterKeys.credentials(makerspaceId) }); } });
  const name = credentialPerson(row.user, names);
  const locked = row.locked_until && new Date(row.locked_until).getTime() > Date.now();
  return <li className="grid gap-2 rounded-2xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center gap-3">
      <div className="min-w-0 flex-1"><p className="title-section break-words">{name}</p>
        <p className="text-sm text-muted">{row.kind === "pin" ? t`PIN` : t`NFC tag`}{row.label ? ` · ${row.label}` : ""}{" · "}
          {row.last_used_at ? <>{t`Used `}<RelativeTime date={row.last_used_at} /></> : t`Never used`}</p></div>
      {row.disabled_at ? <StatusPill label={t`Disabled`} tone="neutral" /> : locked ? <StatusPill label={t`Locked after wrong tries`} tone="warn" /> : <StatusPill label={t`Active`} tone="success" />}
      {row.disabled_at ? null : confirming ? <span className="flex gap-2"><button type="button" className="desk-button" onClick={() => setConfirming(false)}>{t`Keep`}</button>
        <button type="button" className="desk-button-danger" disabled={disable.isPending} onClick={() => disable.mutate()}>{t`Disable`}</button></span>
        : <button type="button" className="desk-button" aria-label={row.kind === "pin" ? t`Disable PIN for ${name}` : t`Disable NFC tag for ${name}`} onClick={() => setConfirming(true)}>{t`Disable`}</button>}
    </div>
    {disable.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(disable.error)}</p> : null}
  </li>;
}

/** Members' door and machine credentials (decision 312, child switch `machines.integrations.access`): digests only, never the secret. */
export function AdapterCredentials({ makerspaceId }: { makerspaceId: number }) {
  const list = useQuery({ queryKey: adapterKeys.credentials(makerspaceId), queryFn: () => adaptersApi.credentials(makerspaceId) });
  const members = useQuery({ queryKey: ["device-adapters", makerspaceId, "member-names"], staleTime: 60_000,
    queryFn: () => staffRequest<{ results: Member[] }>(`/admin/memberships?${new URLSearchParams({ makerspace_id: String(makerspaceId), status: "active", page_size: "500" })}`) });
  const names = new Map((members.data?.results ?? []).map(row => [row.user.id, row.user.display_name || row.user.username] as [number, string]));
  return <div className="grid gap-6">
    <AddCredential makerspaceId={makerspaceId} />
    {list.isError ? <p role="alert" className="text-sm text-danger">{adapterErrorMessage(list.error)}</p> : null}
    {list.data?.length ? <ul className="grid gap-3" aria-label={t`Credentials`}>{list.data.map(row => <CredentialRow key={row.id} row={row} makerspaceId={makerspaceId} names={names} />)}</ul>
      : <p className="text-sm text-muted">{list.isLoading ? t`Loading…` : t`No credentials yet.`}</p>}
  </div>;
}
