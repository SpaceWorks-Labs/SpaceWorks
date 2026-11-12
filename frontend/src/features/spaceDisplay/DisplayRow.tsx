import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { ActionControl } from "../../components/ui";
import { presenceErrorText } from "../presence/presenceCopy";
import { adminDisplayApi, type AdminDisplay } from "./api";
import { anthiasApi, type AnthiasPlayer } from "./anthiasApi";
import { DisplayConfigFields, draftOf, toInput } from "./DisplayConfigFields";
import { DisplayPreview } from "./DisplayPreview";
import { ScreenLinkBlock } from "./ScreenLinkBlock";

function PlayerChoice({ players, chosen, busy, onChange }: { players: AnthiasPlayer[]; chosen: number[]; busy: boolean; onChange: (ids: number[]) => void }) {
  if (!players.length) return null;
  return <fieldset className="grid gap-1" disabled={busy}><legend className="text-sm font-semibold text-ink">{t`Show on these Anthias players`}</legend>
    {players.map((player) => <label key={player.id} className="flex min-h-11 items-center gap-3 text-sm">
      <input type="checkbox" className="h-5 w-5 accent-accent" checked={chosen.includes(player.id)}
        onChange={(e) => onChange(e.target.checked ? [...chosen, player.id] : chosen.filter((id) => id !== player.id))} />{player.name}
    </label>)}
  </fieldset>;
}

/** `issuedUrl` is the address from this page's provision or New address response; lists never carry it (L-D3). */
export function DisplayRow({ makerspaceId, spaceName, row, players, onChanged, issuedUrl = "", onIssued }:
  { makerspaceId: number; spaceName: string; row: AdminDisplay; players: AnthiasPlayer[]; onChanged: () => void;
    issuedUrl?: string; onIssued?: (url: string) => void }) {
  const [draft, setDraft] = useState(() => draftOf(row));
  const save = useMutation({ mutationFn: () => adminDisplayApi.update(makerspaceId, row.id, toInput(draft)), onSuccess: onChanged });
  const unpair = useMutation({ mutationFn: () => adminDisplayApi.unpair(makerspaceId, row.id), onSuccess: onChanged });
  const rotate = useMutation({ mutationFn: () => adminDisplayApi.rotateLink(makerspaceId, row.id),
    onSuccess: (next) => { onIssued?.(next.url); onChanged(); } });
  const choose = useMutation({ mutationFn: (ids: number[]) => anthiasApi.setPlayers(makerspaceId, row.id, ids), onSuccess: onChanged });
  const error = save.error ?? unpair.error ?? rotate.error ?? choose.error;
  return <li className="grid gap-3 rounded-xl border border-line bg-panel p-4">
    <p className="flex items-center justify-between gap-3"><span className="font-semibold">{row.name || t`Unnamed screen`}</span>
      <span className="text-sm text-muted">{row.online ? t`Online` : t`Offline`}</span></p>
    <DisplayConfigFields draft={draft} setDraft={setDraft} />
    <DisplayPreview draft={draft} spaceName={spaceName} />
    {row.has_link ? <ScreenLinkBlock row={row} url={issuedUrl} busy={rotate.isPending} onRotate={() => rotate.mutate()} /> : null}
    {row.has_link ? <PlayerChoice players={players} chosen={row.player_ids} busy={choose.isPending} onChange={(ids) => choose.mutate(ids)} /> : null}
    {error ? <p role="alert" className="text-sm text-danger">{presenceErrorText(error).text}</p> : null}
    <div className="flex flex-wrap gap-2">
      <ActionControl primary action={{ label: t`Save changes`, pending: save.isPending, disabled: draft.panels.length === 0,
        disabledReason: t`Choose at least one section.`, onClick: () => save.mutate() }} />
      <ActionControl action={{ label: t`Unpair`, tone: "danger", pending: unpair.isPending, onClick: () => unpair.mutate(),
        confirm: { title: t`Unpair this screen?`, message: t`The screen stops showing this space at once and shows a new pairing code.`, confirmLabel: t`Unpair` } }} />
    </div>
  </li>;
}
