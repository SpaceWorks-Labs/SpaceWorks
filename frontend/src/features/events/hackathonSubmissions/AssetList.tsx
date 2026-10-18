import { useQueries } from "@tanstack/react-query";
import { memberRequest, memberRequestBlob } from "../../../lib/api";
import { ActionControl, Card } from "../../../components/ui";
import { memberBase, teamBase, submissionKey } from "./api";
import type { Asset, SubmissionScope } from "./types";
import { AssetPreview } from "./AssetPreview";
import { OriginalVideo } from "./OriginalVideo";
import { TextTablePreview } from "./TextTablePreview";

export function AssetList({ scope, assetIds, publicIds, onConsent, onRemove, disabled }: {
  scope: SubmissionScope; assetIds: number[]; publicIds: number[]; disabled: boolean;
  onConsent: (id: number, value: boolean) => void; onRemove: (id: number) => void;
}) {
  const queries = useQueries({ queries: assetIds.map(id => ({
    queryKey: [...submissionKey(scope), "asset", id],
    queryFn: () => memberRequest<Asset>(`${teamBase(scope)}assets/${id}/`),
    retry: false, refetchInterval: (query: { state: { data: Asset | undefined } }) =>
      ["ready", "rejected", "quarantined", "aborted", "expired"].includes(query.state.data?.state ?? "") ? false : 2000,
  })) });
  async function download(id: number) {
    const blob = await memberRequestBlob(`${memberBase(scope)}assets/${id}/download/`);
    const url = URL.createObjectURL(blob), anchor = document.createElement("a");
    anchor.href = url; anchor.download = `project-file-${id}`; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }
  return <section aria-label="Project files" className="grid gap-3">
    {assetIds.map((id, index) => <Card key={id}><div className="grid gap-3">
      <p className="text-sm text-ink">File {id}: <span role="status">{queries[index].isError ? "Status unavailable" : queries[index].data?.state ?? "Loading…"}</span></p>
      <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" disabled={disabled} checked={publicIds.includes(id)}
        onChange={event => onConsent(id, event.target.checked)} />Allow this file in the published project gallery</label>
      <div className="flex flex-wrap gap-3"><ActionControl action={{ label: `Download file ${id}`, disabled: queries[index].data?.state !== "ready", onClick: () => { void download(id).catch(() => queries[index].refetch()); } }} />
        <ActionControl action={{ label: `Remove file ${id} from draft`, disabled, onClick: () => onRemove(id) }} /></div>
      {queries[index].data?.state === "ready" && ((queries[index].data?.kind === "hardware-pcb" &&
        /^(?:gbr|ger|gt[lsop]|gb[lsop]|gko|gm1|g\d+|drl|xln|zip)$/.test(queries[index].data?.extension ?? "")) ||
        ["stl", "obj", "3mf", "gcode.3mf", "step", "stp", "iges", "igs"].includes(queries[index].data?.extension ?? "")) ?
        <AssetPreview assetId={id} bytes={queries[index].data?.bytes ?? 0}
          filename={queries[index].data?.filename ?? `file-${id}`} extension={queries[index].data?.extension ?? ""}
          load={() => memberRequestBlob(`${memberBase(scope)}assets/${id}/preview/`)}
          download={() => { void download(id).catch(() => queries[index].refetch()); }} /> : null}
      {queries[index].data?.state === "ready" && queries[index].data?.kind === "video" ?
        <OriginalVideo bytes={queries[index].data?.bytes ?? 0} playable={queries[index].data?.media_metadata?.browser_playable === true}
          load={() => memberRequestBlob(`${memberBase(scope)}assets/${id}/download/`)}
          download={() => { void download(id).catch(() => queries[index].refetch()); }} /> : null}
      {queries[index].data?.state === "ready" && /^(?:csv|pos|ino|py|c|h|cpp|hpp|cc|hex|scad|gcode|gco|g|nc|tap|ngc|cnc|asc)$/.test(queries[index].data?.extension ?? "") ?
        <TextTablePreview bytes={queries[index].data?.bytes ?? 0} table={queries[index].data?.extension === "csv"}
          load={() => memberRequestBlob(`${memberBase(scope)}assets/${id}/preview/`)}
          download={() => { void download(id).catch(() => queries[index].refetch()); }} /> : null}
    </div></Card>)}
  </section>;
}
