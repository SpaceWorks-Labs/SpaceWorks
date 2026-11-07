import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState } from "react";
import { Pause } from "lucide-react";
import { ActionControl, Field } from "../../../components/ui";
import { uploadProjectFile } from "./upload";
import type { Asset, SubmissionScope, UploadSpec } from "./types";

export function UploadEditor({ scope, allowedOrigins, options, onUploaded, disabled, onPendingChange }: {
  scope: SubmissionScope; allowedOrigins: readonly string[]; options: readonly (UploadSpec & { label: string })[];
  onUploaded: (asset: Asset) => void; disabled?: boolean; onPendingChange?: (pending: boolean) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [option, setOption] = useState(0);
  const [progress, setProgress] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { onPendingChange?.(pending); return () => onPendingChange?.(false); }, [pending, onPendingChange]);
  async function upload() {
    if (!file || !options[option]) return;
    setError(""); setPending(true); controller.current = new AbortController();
    try {
      const asset = await uploadProjectFile({ file, scope, spec: options[option], allowedOrigins,
        signal: controller.current.signal, progress: setProgress });
      onUploaded(asset); setFile(null); setProgress(0);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t`Upload interrupted. Select the same file to resume.`);
    } finally { setPending(false); }
  }
  return <fieldset disabled={disabled} className="grid gap-4">
    <legend className="text-lg font-semibold text-ink">{t`Upload maker files`}</legend>
    <p className="text-sm text-muted">{t`Upload CAD, PCB, firmware, fabrication files, images, a deck or video. Files are checked before they can be submitted.`}</p>
    <Field label={t`File format`} hint={t`Choose the content variant exported by your tool.`}><select disabled={pending} value={option} className="desk-input min-h-11"
      onChange={event => setOption(Number(event.target.value))}>{options.map((format, index) => <option key={`${format.group}:${format.subtype}:${index}`} value={index}>{format.label}</option>)}</select></Field>
    <Field label={t`Project file`} error={error || undefined}><input disabled={pending} type="file" className="desk-input min-h-11"
      onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
    <div role="status" aria-live="polite" className="text-sm text-muted">{pending ? t`Uploaded ${Math.round(progress / Math.max(file?.size ?? 1, 1) * 100)}%` : t`Interrupted uploads can resume after you select the original file.`}</div>
    <ActionControl primary action={{ label: t`Upload file`, disabled: !file || !options.length, pending,
      onClick: () => void upload() }} />
    {pending ? <button type="button" className="desk-button min-h-11 gap-2" onClick={() => controller.current?.abort()}>
      <Pause aria-hidden size={20} />{t`Pause upload`}</button> : null}
  </fieldset>;
}
