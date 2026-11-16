// The space's artwork library (decision 344(b)): every background, image and watermark the space uploaded, reusable
// in this design as a background or an image layer. Deleting gives the storage back and is refused while any design,
// saved version or template still uses the picture (the server checks; the message says so).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { t } from "@lingui/core/macro";
import { useState } from "react";

import { staffRequest } from "../../lib/api";
import { BoxSpinner } from "../BoxSpinner";
import { ErrorText } from "../ui/ErrorText";
import type { Background, Layer, Side } from "./cardTypes";
import { useAssetUrl } from "./CardLayerView";
import { MAX_LAYERS, newLayer } from "./designDocument";
import { UploadButton } from "./BackgroundPicker";

export type LibraryAsset = { asset_id: string; kind: "background" | "watermark" | "image"; width_px: number; height_px: number;
  mean_colour: string; size_bytes: number; created_at: string };

const libraryKey = (designId: number) => ["card-design-asset-library", designId] as const;

export function useAssetLibrary(designId: number) {
  return useQuery({ queryKey: libraryKey(designId), enabled: designId > 0, staleTime: 30_000,
    queryFn: () => staffRequest<LibraryAsset[]>(`/admin/card-designs/${designId}/asset-library`) });
}

function Thumb({ designId, asset }: { designId: number; asset: LibraryAsset }) {
  const url = useAssetUrl(designId, asset.asset_id);
  return <div className="grid aspect-[4/3] w-full place-items-center overflow-hidden rounded-control border border-line"
    style={{ background: /^#[0-9A-F]{6}$/i.test(asset.mean_colour) ? asset.mean_colour : undefined }}>
    {url ? <img src={url} alt="" className="h-full w-full object-cover" /> : <BoxSpinner size={20} mono />}
  </div>;
}

export function AssetLibrary({ designId, side, stock, readOnly, onBackground, onAdd, onAssetColour }: {
  designId: number; side: Side; stock: string; readOnly: boolean; onBackground: (background: Background) => void;
  onAdd: (layer: Layer) => void; onAssetColour: (assetId: string, colour: string) => void;
}) {
  const client = useQueryClient();
  const library = useAssetLibrary(designId);
  const [message, setMessage] = useState<string | null>(null);
  const remove = useMutation({
    mutationFn: (assetId: string) => staffRequest<void>(`/admin/card-designs/${designId}/asset-library/${assetId}`, { method: "DELETE" }),
    onSuccess: () => { setMessage(t`Picture deleted; its storage is free again.`); void client.invalidateQueries({ queryKey: libraryKey(designId) }); },
  });
  const full = side.layers.length >= MAX_LAYERS;
  const use = (asset: LibraryAsset, how: "background" | "layer") => {
    onAssetColour(asset.asset_id, asset.mean_colour);
    if (how === "background") onBackground({ kind: "image", asset_id: asset.asset_id, fit: "cover", dim_pct: 0, fallback: asset.mean_colour || "#FFFFFF" });
    else onAdd(newLayer("image", side, stock, { asset_id: asset.asset_id }));
  };
  return <div className="grid gap-3">
    <p className="text-xs text-muted">{t`Pictures uploaded in any design of this space. Use one here, or delete one nothing uses any more.`}</p>
    {readOnly ? null : <UploadButton designId={designId} kind="image" label={t`Upload a picture`}
      onUploaded={() => void client.invalidateQueries({ queryKey: libraryKey(designId) })} />}
    {library.isLoading ? <BoxSpinner size={24} mono /> : null}
    {library.isError ? <ErrorText message={t`The library couldn't be loaded.`} /> : null}
    {library.data && !library.data.length ? <p className="text-sm text-muted">{t`No pictures yet.`}</p> : null}
    <ul className="grid grid-cols-2 gap-2">
      {library.data?.map((asset) => <li key={asset.asset_id} className="grid gap-1">
        <Thumb designId={designId} asset={asset} />
        <span className="text-[11px] text-muted">{t`${asset.width_px} × ${asset.height_px} px`}</span>
        {readOnly ? null : <div className="grid gap-1">
          <button type="button" className="desk-button-ghost min-h-11 text-xs" onClick={() => use(asset, "background")}>{t`Background`}</button>
          <button type="button" className="desk-button-ghost min-h-11 text-xs" disabled={full} onClick={() => use(asset, "layer")}>{t`Add to card`}</button>
          <button type="button" className="desk-button-ghost min-h-11 text-xs text-danger" disabled={remove.isPending}
            onClick={() => { if (window.confirm(t`Delete this picture from the space's library?`)) { setMessage(null); remove.mutate(asset.asset_id); } }}>
            {t`Delete`}</button>
        </div>}
      </li>)}
    </ul>
    {remove.error ? <ErrorText message={remove.error.message} /> : null}
    {message ? <p role="status" className="text-sm text-muted">{message}</p> : null}
  </div>;
}
