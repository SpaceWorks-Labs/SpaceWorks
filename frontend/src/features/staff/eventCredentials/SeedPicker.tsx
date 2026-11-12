import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { CommandSession } from "../../events/hackathonAdmission/transport";
import type { LayerDocument, Stock } from "./layout";
import { LogoLoader } from "../../../components/LogoLoader";

export type InstalledSeed = { id: number; event_id: number; event_version: number; kind: string; document: LayerDocument; stock: Stock | null };
type Seed = { seed_id: string; seed_version: number; document: LayerDocument };
export function SeedPicker({ eventId, version, kind, stock, onInstall }: {
  eventId: number; version?: number; kind: "badge" | "certificate"; stock?: Stock; onInstall: (value: InstalledSeed) => void;
}) {
  const [theme, setTheme] = useState("light");
  const [url, setUrl] = useState<string | null>(null);
  const commands = useRef(new CommandSession());
  const selection = (seed: Seed) => ({ kind, theme, seed_id: seed.seed_id, seed_version: seed.seed_version, stock: stock ?? null });
  const query = useQuery({ queryKey: ["event-design-seeds", eventId, kind, theme, stock],
    queryFn: () => staffRequest<{ results: Seed[] }>(`/admin/events/${eventId}/design-seeds/?kind=${kind}&theme=${theme}${stock ? `&stock=${stock}` : ""}`) });
  const install = useMutation({ mutationFn: (seed: Seed) => commands.current.send<InstalledSeed>(
    `/api/v1/admin/events/${eventId}/design-seeds/install/`, "POST", { ...selection(seed), expected_version: version }, true), onSuccess: onInstall });
  const preview = useMutation({ mutationFn: (seed: Seed) => staffRequestBlob(`/admin/events/${eventId}/design-seeds/preview.pdf`, {
    method: "POST", body: JSON.stringify(selection(seed)),
  }), onSuccess: (blob) => setUrl(URL.createObjectURL(blob)) });
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  const error = query.error || install.error || preview.error;
  return <fieldset className="grid gap-3 rounded-control border border-line p-3" disabled={install.isPending || preview.isPending}>
    <legend className="font-semibold">{t`Default designs`}</legend>
    <label className="grid gap-1 text-sm">{t`Theme`}<select className="desk-input" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="light">{t`Light`}</option><option value="dark">{t`Dark`}</option></select></label>
    {query.isPending ? <LogoLoader label={t`Loading designs…`} size={48} className="min-h-16 py-3" /> : null}
    {query.data?.results.map((seed) => <div className="flex flex-wrap items-center gap-2" key={seed.seed_id}>
      <span className="text-sm">{seed.seed_id.replace(/-/g, " ")}</span>
      <button className="desk-button" type="button" onClick={() => preview.mutate(seed)}>{t`Preview sample`}</button>
      <button className="desk-button" type="button" disabled={version === undefined} onClick={() => install.mutate(seed)}>{t`Install design`}</button>
    </div>)}
    {url ? <><iframe className="h-80 w-full border border-line" src={url} title={t`Default design sample PDF`} /><button className="desk-button" type="button" onClick={() => setUrl(null)}>{t`Close sample`}</button></> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </fieldset>;
}
