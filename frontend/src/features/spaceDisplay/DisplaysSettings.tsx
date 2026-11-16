import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ActionControl, Field, SettingsSection } from "../../components/ui";
import { presenceErrorText } from "../presence/presenceCopy";
import { AnthiasSettings } from "./AnthiasSettings";
import { anthiasApi, anthiasKeys } from "./anthiasApi";
import { blank, DisplayConfigFields, toInput } from "./DisplayConfigFields";
import { DisplayRow } from "./DisplayRow";
import { PublicPageSettings } from "./PublicPageSettings";
import { adminDisplayApi, spaceNowKeys } from "./api";

export { panelLabel } from "./DisplayConfigFields";

/** Settings, Display screens (decisions 307c, 325): pair or link screens, set what they show, Anthias, the public page. */
export function DisplaysSettings({ makerspaceId, spaceName = "" }: { makerspaceId: number; spaceName?: string }) {
  const client = useQueryClient();
  const key = spaceNowKeys.admin(makerspaceId);
  const list = useQuery({ queryKey: key, queryFn: () => adminDisplayApi.list(makerspaceId), refetchInterval: 30_000 });
  const anthias = useQuery({ queryKey: anthiasKeys.players(makerspaceId), queryFn: () => anthiasApi.list(makerspaceId), retry: false });
  const [code, setCode] = useState("");
  const [draft, setDraft] = useState(blank);
  /** Addresses made on this page, by screen id: the only time the server returns one (L-D3). */
  const [issued, setIssued] = useState<Record<number, string>>({});
  const refresh = () => { void client.invalidateQueries({ queryKey: key }); void client.invalidateQueries({ queryKey: anthiasKeys.players(makerspaceId) }); };
  const claim = useMutation({ mutationFn: () => adminDisplayApi.claim(makerspaceId, { code: code.trim(), ...toInput(draft) }),
    onSuccess: () => { setCode(""); setDraft(blank); refresh(); } });
  const link = useMutation({ mutationFn: () => adminDisplayApi.provision(makerspaceId, toInput(draft)),
    onSuccess: (made) => { setIssued((old) => ({ ...old, [made.id]: made.url })); setDraft(blank); refresh(); } });
  const players = anthias.data?.players ?? [];
  const error = claim.error ?? link.error;
  return <SettingsSection title={t`Display screens`}
    description={t`Show who is here, events, machines and public stats on a TV. A screen shows only what a visitor who is not signed in can see.`}>
    {list.isError ? <p role="alert" className="py-3 text-sm text-danger">{presenceErrorText(list.error).text}</p> : null}
    <div className="grid gap-3 py-3">
      <h3 className="text-base font-semibold">{t`Add a screen`}</h3>
      <Field label={t`Pairing code`} hint={t`Open /display on a TV or kiosk browser and enter the code it shows. Or make a link instead, for players that cannot type a code, such as Anthias.`}>
        <input className="desk-input font-mono uppercase tracking-widest" maxLength={8} autoComplete="off" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} /></Field>
      <DisplayConfigFields draft={draft} setDraft={setDraft} />
      {error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(error).text}</p> : null}
      <div className="flex flex-wrap gap-2">
        <ActionControl primary action={{ label: t`Pair screen`, pending: claim.isPending, disabled: code.trim().length < 4 || draft.panels.length === 0,
          disabledReason: t`Enter the code shown on the screen and choose a section.`, onClick: () => claim.mutate() }} />
        <ActionControl action={{ label: t`Make a screen link`, pending: link.isPending, disabled: draft.panels.length === 0, onClick: () => link.mutate() }} />
      </div>
    </div>
    <ul className="grid gap-3 py-3" aria-label={t`Paired screens`}>
      {(list.data?.displays ?? []).map((row) => <DisplayRow key={`${row.id}-${row.player_ids.join()}`} makerspaceId={makerspaceId} spaceName={spaceName || t`Your space`} row={row} players={players} onChanged={refresh} issuedUrl={issued[row.id]}
        onIssued={(url) => setIssued((old) => ({ ...old, [row.id]: url }))} />)}
    </ul>
    {anthias.data?.enabled ? <div className="py-3"><AnthiasSettings makerspaceId={makerspaceId} players={players} allowPrivate={anthias.data.allow_private_hosts} /></div> : null}
    <div className="py-3"><PublicPageSettings makerspaceId={makerspaceId} /></div>
  </SettingsSection>;
}
