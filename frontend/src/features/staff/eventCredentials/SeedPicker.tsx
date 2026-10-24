import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../../lib/api";
import { CommandSession } from "../../events/hackathonAdmission/transport";
import type { LayerDocument, Stock } from "./layout";

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
    <legend className="font-semibold">Default designs</legend>
    <label className="grid gap-1 text-sm">Theme<select className="desk-input" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="light">Light</option><option value="dark">Dark</option></select></label>
    {query.isPending ? <p role="status">Loading designs?</p> : null}
    {query.data?.results.map((seed) => <div className="flex flex-wrap items-center gap-2" key={seed.seed_id}>
      <span className="text-sm">{seed.seed_id.replace(/-/g, " ")}</span>
      <button className="desk-button" type="button" onClick={() => preview.mutate(seed)}>Preview sample</button>
      <button className="desk-button" type="button" disabled={version === undefined} onClick={() => install.mutate(seed)}>Install design</button>
    </div>)}
    {url ? <><iframe className="h-80 w-full border border-line" src={url} title="Default design sample PDF" /><button className="desk-button" type="button" onClick={() => setUrl(null)}>Close sample</button></> : null}
    {error ? <p role="alert" className="text-sm text-danger">{error.message}</p> : null}
  </fieldset>;
}
