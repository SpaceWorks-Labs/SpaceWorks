import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { pageInput, pageLabel } from "./documentDefaults";
import { PageImage } from "./PageImage";
import type { PageOperation } from "./pageApi";
import type { EditorState } from "./pageTypes";

export function PageEditorAssets({ state, pending, dirty, run }: {
  state: EditorState; pending: boolean; dirty: boolean; run: (input: PageOperation) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [alt, setAlt] = useState("");
  const [error, setError] = useState("");
  const [inputKey, setInputKey] = useState(0);
  useEffect(() => { setFile(null); setAlt(""); setInputKey(key => key + 1); }, [state.version]);
  const disabled = pending || dirty || !state.capabilities.can_edit_details;
  const maxBytes = state.limits.upload_bytes;
  const remainingBytes = state.limits.storage_bytes === null ? Infinity : Math.max(0, state.limits.storage_bytes - state.limits.storage_bytes_used);
  return <section aria-label={t`Page images`} className="grid gap-4">
    <h3 className="title-section">{t`Private page images`}</h3>
    <p className="text-sm text-muted">{t`Retained revisions pin their images. A new cover leaves the published cover available until you publish again. Save your draft before managing images.`}</p>
    <form className="grid gap-3" onSubmit={e => {
      e.preventDefault(); if (!file || disabled) return;
      if (file.size > maxBytes) { setError(t`Choose an image smaller than ${maxBytes.toLocaleString(formatLocale())} bytes.`); return; }
      setError(""); run({ action: "upload", version: state.version, file, alt_text: alt });
    }}>
      <fieldset disabled={disabled} className="grid gap-3">
        <legend className="sr-only">{t`Upload page image`}</legend>
        <label className={pageLabel}>{t`Image description`}<input className={pageInput} required maxLength={200} value={alt} onChange={e => setAlt(e.target.value)} /></label>
        <label className={pageLabel}>{t`JPEG, PNG or WebP image`}<input key={inputKey} className={pageInput} type="file" required accept="image/jpeg,image/png,image/webp" onChange={e => setFile(e.target.files?.[0] ?? null)} /></label>
        <button className="desk-button justify-self-start" type="submit" disabled={!file || !alt.trim() || state.assets.length >= state.limits.assets || remainingBytes < (file?.size ?? 0)}>{t`Upload image`}</button>
      </fieldset>
    </form>
    {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    <ul className="grid gap-3 sm:grid-cols-2">{state.assets.map(asset => <li key={asset.id} className="grid content-start gap-3 rounded-xl border border-line p-3">
      <PageImage url={asset.preview_url} alt={asset.alt_text} token={String(state.version)} privatePreview />
      <p className="text-sm">{asset.alt_text}{asset.pinned ? t` · Retained by a revision` : ""}</p>
      <button className="desk-button-danger-outline justify-self-start" type="button" disabled={disabled || asset.pinned} onClick={() => run({ action: "delete_asset", version: state.version, id: asset.id })}>{t`Delete ${asset.alt_text}`}</button>
    </li>)}</ul>
  </section>;
}
