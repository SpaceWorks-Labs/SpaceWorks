import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ImagePlus, Trash2 } from "lucide-react";
import { staffRequest } from "../../../lib/api";
import { uploadPublicImage } from "../ImageUploader";
import { CoverPhotoEditor } from "./CoverPhotoEditor";

/**
 * An event's or a series' public cover (B4): the current picture, and the full cover editor to replace it.
 * Upload is the existing presign -> storage -> attach flow; the server converts the result to WebP.
 */
export function EventCoverUploader({ endpoint, currentUrl, label, disabled = false, onChanged }: {
  endpoint: string; currentUrl: string | null | undefined; label: string; disabled?: boolean; onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState("");
  const remove = async () => {
    setRemoving(true); setError("");
    try { await staffRequest(endpoint, { method: "DELETE" }); onChanged(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : t`Could not remove the cover.`); }
    finally { setRemoving(false); }
  };
  return <div className="grid min-w-0 gap-3">
    <p className="text-sm font-semibold text-ink">{label}</p>
    <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center">
      <div className="aspect-[16/7] w-full shrink-0 overflow-hidden rounded-lg border border-line bg-surface sm:w-56">
        {currentUrl ? <img src={currentUrl} alt={label} className="h-full w-full object-cover" />
          : <div className="grid h-full w-full place-items-center text-xs text-muted">{t`No cover yet`}</div>}
      </div>
      {!editing ? <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button" disabled={disabled} onClick={() => setEditing(true)}>
          <ImagePlus size={18} aria-hidden="true" />{currentUrl ? t`Replace cover` : t`Add a cover`}</button>
        {currentUrl ? <button type="button" className="desk-button-danger-outline" disabled={disabled || removing} onClick={() => { void remove(); }}>
          <Trash2 size={18} aria-hidden="true" />{t`Remove cover`}</button> : null}
      </div> : null}
    </div>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    {editing && !disabled ? <CoverPhotoEditor title={label} describe={false} onCancel={() => setEditing(false)}
      onSave={async file => { await uploadPublicImage(endpoint, file); setEditing(false); onChanged(); }} /> : null}
  </div>;
}
