import { t } from "@lingui/core/macro";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ActionControl, Field } from "../../components/ui";
import { presenceErrorText } from "../presence/presenceCopy";
import { anthiasApi, anthiasKeys, type AnthiasPlayer, type AnthiasTest } from "./anthiasApi";

const REASONS = (): Record<string, string> => ({
  auth_failed: t`The player refused the username or password.`, unreachable: t`The player could not be reached.`,
  timeout: t`The player took too long to answer.`, dns_failed: t`That host name could not be found.`,
  blocked_address: t`That address is not allowed (loopback, link-local or cloud metadata).`,
  private_address: t`This deployment does not allow players on a private network.`,
  not_found: t`That host does not look like Anthias.`, no_link: t`A screen has no address yet. Create it as a screen link.`,
  http_error: t`The player answered with an error.`, bad_response: t`The player sent something unexpected.`,
  failed: t`The player did not answer as expected. Check the address, username and password.` });
export const reasonText = (code: string) => REASONS()[code] ?? code;

function PlayerRow({ makerspaceId, player, onChanged }: { makerspaceId: number; player: AnthiasPlayer; onChanged: () => void }) {
  const [tested, setTested] = useState<AnthiasTest | null>(null);
  const test = useMutation({ mutationFn: () => anthiasApi.test(makerspaceId, player.id), onSuccess: (r) => { setTested(r); onChanged(); } });
  const sync = useMutation({ mutationFn: () => anthiasApi.sync(makerspaceId, player.id), onSuccess: onChanged });
  const remove = useMutation({ mutationFn: () => anthiasApi.remove(makerspaceId, player.id), onSuccess: onChanged });
  const error = test.error ?? sync.error ?? remove.error;
  const status = player.status === "ok" ? t`In sync` : player.status === "error" ? t`Error: ${reasonText(player.last_error)}` : t`Not synced yet`;
  return <li className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <p className="flex flex-wrap items-baseline justify-between gap-2"><span className="font-semibold">{player.name}</span>
      <span className="break-all font-mono text-xs text-muted">{player.host_url}</span></p>
    <p className={`text-sm ${player.status === "error" ? "text-danger" : "text-muted"}`} role="status">{status}
      {player.last_synced_at ? ` · ${new Date(player.last_synced_at).toLocaleString()}` : ""}</p>
    {player.api_version ? <p className="text-xs text-muted">{t`Anthias ${player.anthias_version || "?"}, API ${player.api_version}`}</p> : null}
    {tested ? <p role="status" className={`text-sm ${tested.ok ? "text-success-ink" : "text-danger"}`}>
      {tested.ok ? t`Connected. Anthias ${tested.anthias_version || "?"}, API ${tested.api_version}.` : reasonText(tested.reason)}</p> : null}
    {error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(error).text}</p> : null}
    <div className="flex flex-wrap gap-2">
      <ActionControl action={{ label: t`Test connection`, pending: test.isPending, onClick: () => test.mutate() }} />
      <ActionControl action={{ label: t`Sync now`, pending: sync.isPending, onClick: () => sync.mutate() }} />
      <ActionControl action={{ label: t`Remove`, tone: "danger", pending: remove.isPending, onClick: () => remove.mutate(),
        confirm: { title: t`Remove this player?`, message: t`SpaceWorks deletes the web assets it made on the player, then forgets it.`, confirmLabel: t`Remove` } }} />
    </div>
  </li>;
}

/** Players this space registered. The password is write-only: it is stored encrypted and never shown again. */
export function AnthiasSettings({ makerspaceId, players, allowPrivate }: { makerspaceId: number; players: AnthiasPlayer[]; allowPrivate: boolean }) {
  const client = useQueryClient();
  const refresh = () => void client.invalidateQueries({ queryKey: anthiasKeys.players(makerspaceId) });
  const [form, setForm] = useState({ name: "", host_url: "", username: "", password: "" });
  const add = useMutation({ mutationFn: () => anthiasApi.create(makerspaceId, form), onSuccess: () => { setForm({ name: "", host_url: "", username: "", password: "" }); refresh(); } });
  return <div className="grid gap-3">
    <h3 className="text-base font-semibold">{t`Anthias players`}</h3>
    <p className="text-sm text-muted">{allowPrivate ? t`Players usually sit on your local network, for example http://192.168.1.20.` : t`This deployment only allows players on public addresses.`}
      {" "}{t`SpaceWorks keeps one web asset per screen on each player you choose.`}</p>
    <ul className="grid gap-3" aria-label={t`Anthias players`}>{players.map((p) => <PlayerRow key={`${p.id}-${p.status}-${p.last_synced_at}`} makerspaceId={makerspaceId} player={p} onChanged={refresh} />)}</ul>
    <div className="grid gap-3 sm:grid-cols-2">
      <Field label={t`Player name`}><input className="desk-input" maxLength={80} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
      <Field label={t`Player address`} hint={t`Starts with http:// or https://, no path.`}><input className="desk-input" inputMode="url" value={form.host_url} onChange={(e) => setForm({ ...form, host_url: e.target.value })} /></Field>
      <Field label={t`Username (optional)`}><input className="desk-input" autoComplete="off" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
      <Field label={t`Password (optional)`} hint={t`Stored encrypted. It is never shown again.`}><input className="desk-input" type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
    </div>
    {add.error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(add.error).text}</p> : null}
    <div><ActionControl primary action={{ label: t`Add player`, pending: add.isPending, disabled: !form.name.trim() || !form.host_url.trim(),
      disabledReason: t`Enter a name and an address.`, onClick: () => add.mutate() }} /></div>
  </div>;
}
