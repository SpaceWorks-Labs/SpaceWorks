// The side's background (colour, gradient or uploaded image) and the card-wide watermark.
import { t } from "@lingui/core/macro";
import { useState } from "react";

import type { Background, Watermark } from "./cardTypes";
import { uploadAsset } from "./designerApi";
import { ColourInput, NumberInput, SelectInput } from "./inspectorFields";

const ACCEPT = "image/png,image/jpeg,image/webp";

export function UploadButton({ designId, kind, label, onUploaded, disabled }: {
  designId: number; kind: "background" | "watermark" | "image"; label: string; disabled?: boolean;
  onUploaded: (assetId: string, meanColour: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  return <div className="grid gap-1">
    <label className={`desk-button min-h-11 cursor-pointer text-center ${disabled || busy ? "pointer-events-none opacity-60" : ""}`}>
      {busy ? t`Uploading…` : label}
      <input type="file" accept={ACCEPT} className="sr-only" disabled={disabled || busy} onChange={async (event) => {
        const file = event.target.files?.[0];
        event.target.value = "";
        if (!file) return;
        setBusy(true); setFailure(null);
        try {
          const asset = await uploadAsset(designId, kind, file);
          onUploaded(asset.asset_id, asset.mean_colour);
        } catch (error) {
          setFailure(error instanceof Error ? error.message : "The image couldn't be uploaded.");
        } finally {
          setBusy(false);
        }
      }} />
    </label>
    {failure ? <p role="alert" className="text-xs text-danger">{failure}</p> : null}
  </div>;
}

export function BackgroundPicker({ designId, background, onChange, onAssetColour, readOnly }: {
  designId: number; background: Background; onChange: (background: Background) => void;
  onAssetColour: (assetId: string, colour: string) => void; readOnly: boolean;
}) {
  // An image background only enters the document once its upload is finished (an empty one cannot save).
  const [choosingImage, setChoosingImage] = useState(false);
  const kind = choosingImage ? "image" : background.kind;
  return <div className="grid gap-3">
    <SelectInput label={t`Background`} value={kind} disabled={readOnly}
      options={[{ value: "colour", label: t`Colour` }, { value: "gradient", label: t`Gradient` }, { value: "image", label: t`Image` }]}
      onChange={(next) => {
        setChoosingImage(next === "image" && background.kind !== "image");
        if (next === "colour") onChange({ kind: "colour", colour: "#FFFFFF" });
        if (next === "gradient") onChange({ kind: "gradient", type: "linear", angle_deg: 135,
          stops: [{ colour: "#006E63", at: 0 }, { colour: "#142C2A", at: 100 }] });
      }} />
    {background.kind === "colour" && !choosingImage ? <ColourInput label={t`Colour`} value={background.colour} disabled={readOnly}
      onChange={(colour) => colour && onChange({ ...background, colour })} /> : null}
    {background.kind === "gradient" && !choosingImage ? <div className="grid gap-2">
      <SelectInput label={t`Gradient type`} value={background.type} disabled={readOnly}
        options={[{ value: "linear", label: t`Linear` }, { value: "radial", label: t`Radial` }]}
        onChange={(type) => onChange({ ...background, type })} />
      {background.type === "linear" ? <NumberInput label={t`Angle`} unit="°" value={background.angle_deg} min={0} max={360} step={5}
        disabled={readOnly} onChange={(angle_deg) => onChange({ ...background, angle_deg })} /> : null}
      {background.stops.map((stop, index) => <div key={index} className="grid grid-cols-[1fr_5.5rem] items-end gap-2">
        <ColourInput label={t`Stop ${index + 1}`} value={stop.colour} disabled={readOnly} onChange={(colour) => colour && onChange({
          ...background, stops: background.stops.map((item, i) => (i === index ? { ...item, colour } : item)) })} />
        <NumberInput label={t`At`} unit="%" value={stop.at} min={0} max={100} step={5} disabled={readOnly} onChange={(at) => onChange({
          ...background, stops: background.stops.map((item, i) => (i === index ? { ...item, at } : item)) })} />
      </div>)}
      <div className="flex flex-wrap gap-2">
        {background.stops.length < 4 ? <button type="button" className="desk-button-ghost min-h-11" disabled={readOnly}
          onClick={() => onChange({ ...background, stops: [...background.stops, { colour: "#FFFFFF", at: 100 }] })}>{t`Add a stop`}</button> : null}
        {background.stops.length > 2 ? <button type="button" className="desk-button-ghost min-h-11" disabled={readOnly}
          onClick={() => onChange({ ...background, stops: background.stops.slice(0, -1) })}>{t`Remove the last stop`}</button> : null}
      </div>
    </div> : null}
    {choosingImage ? <div className="grid gap-1">
      <UploadButton designId={designId} kind="background" disabled={readOnly} label={t`Upload an image`}
        onUploaded={(asset_id, mean) => {
          onAssetColour(asset_id, mean);
          setChoosingImage(false);
          onChange({ kind: "image", asset_id, fit: "cover", dim_pct: 0, fallback: mean });
        }} />
      <p className="text-xs text-muted">{t`PNG, JPEG or WebP. It is checked and stored privately.`}</p>
    </div> : null}
    {background.kind === "image" && !choosingImage ? <div className="grid gap-2">
      <UploadButton designId={designId} kind="background" disabled={readOnly} label={t`Replace the image`}
        onUploaded={(asset_id, mean) => { onAssetColour(asset_id, mean); onChange({ ...background, asset_id, fallback: mean }); }} />
      <SelectInput label={t`Fit`} value={background.fit} disabled={readOnly}
        options={[{ value: "cover", label: t`Fill the card` }, { value: "contain", label: t`Show the whole image` }]}
        onChange={(fit) => onChange({ ...background, fit })} />
      <NumberInput label={t`Darken`} unit="%" value={background.dim_pct} min={0} max={60} step={5} disabled={readOnly}
        onChange={(dim_pct) => onChange({ ...background, dim_pct })} />
    </div> : null}
  </div>;
}

export function WatermarkPicker({ designId, watermark, onChange, onAssetColour, readOnly }: {
  designId: number; watermark: Watermark; onChange: (watermark: Watermark) => void;
  onAssetColour: (assetId: string, colour: string) => void; readOnly: boolean;
}) {
  const [choosingImage, setChoosingImage] = useState(false);
  return <div className="grid gap-3">
    <SelectInput label={t`Watermark`} value={choosingImage ? "image" : watermark.kind} disabled={readOnly}
      options={[{ value: "none", label: t`None` }, { value: "text", label: t`Text` }, { value: "image", label: t`Image` }]}
      onChange={(kind) => {
        const pending = kind === "image" && !watermark.asset_id;
        setChoosingImage(pending);
        if (!pending) onChange({ ...watermark, kind, text: kind === "text" && !watermark.text ? t`MEMBER` : watermark.text });
      }} />
    {watermark.kind === "text" ? <label className="grid gap-1 text-xs font-semibold text-muted"><span>{t`Watermark text`}</span>
      <input className="desk-input min-h-11" maxLength={32} value={watermark.text} disabled={readOnly}
        onChange={(event) => onChange({ ...watermark, text: event.target.value })} /></label> : null}
    {watermark.kind === "image" || choosingImage ? <UploadButton designId={designId} kind="watermark" disabled={readOnly}
      label={watermark.asset_id ? t`Replace the image` : t`Upload an image`}
      onUploaded={(asset_id, mean) => { onAssetColour(asset_id, mean); setChoosingImage(false); onChange({ ...watermark, kind: "image", asset_id }); }} /> : null}
    {watermark.kind !== "none" ? <div className="grid grid-cols-2 gap-2">
      <NumberInput label={t`Strength`} unit="%" value={watermark.opacity_pct} min={4} max={30} step={1} disabled={readOnly}
        onChange={(opacity_pct) => onChange({ ...watermark, opacity_pct })} />
      <NumberInput label={t`Angle`} unit="°" value={watermark.angle_deg} min={-60} max={60} step={5} disabled={readOnly}
        onChange={(angle_deg) => onChange({ ...watermark, angle_deg })} />
      {watermark.kind === "text" ? <ColourInput label={t`Colour`} value={watermark.colour} disabled={readOnly}
        onChange={(colour) => colour && onChange({ ...watermark, colour })} /> : null}
    </div> : null}
  </div>;
}
