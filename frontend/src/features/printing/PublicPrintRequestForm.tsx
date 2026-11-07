import { t } from "@lingui/core/macro";
import type { Dispatch, FormEvent, SetStateAction } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import { Card, EmptyState } from "../../components/ui";
import { FilePicker, TextArea, TextInput } from "./PublicPrintRequestParts";
import type { TypeIntake } from "../inventory/MachineIntakeForm";
import type { PublicFilamentPool } from "./publicApi";

export type FormState = {
  title: string;
  projectBrief: string;
  preferredSettings: string;
  consumablePoolId: string;
  estimatedFilamentGrams: string;
  material: string;
  color: string;
  quantity: number;
  sourceLink: string;
};

export const initialForm: FormState = {
  title: "",
  projectBrief: "",
  preferredSettings: "",
  consumablePoolId: "",
  estimatedFilamentGrams: "",
  material: "",
  color: "",
  quantity: 1,
  sourceLink: "",
};

export function optional(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

// Group active spools by material so same-material filaments are listed together and
// distinguished by color (the public /spools endpoint already orders by material,color).
export function groupPoolsByMaterial(
  pools: PublicFilamentPool[],
): [string, PublicFilamentPool[]][] {
  const groups = new Map<string, PublicFilamentPool[]>();
  for (const pool of pools) {
    const key = pool.material || "Other";
    const bucket = groups.get(key);
    if (bucket) bucket.push(pool);
    else groups.set(key, [pool]);
  }
  return [...groups.entries()];
}

type PrintDetailsFormProps = {
  form: FormState;
  updateField: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  catalogue?: TypeIntake;
  poolsQuery: UseQueryResult<PublicFilamentPool[], Error>;
  modelFiles: File[];
  setModelFiles: Dispatch<SetStateAction<File[]>>;
  screenshotFiles: File[];
  setScreenshotFiles: Dispatch<SetStateAction<File[]>>;
  submitPending: boolean;
  submitError?: Error | null;
  uploadProgress: string;
  website: string;
  onWebsiteChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
};

export function PrintDetailsForm({
  form,
  updateField,
  poolsQuery,
  catalogue,
  modelFiles,
  setModelFiles,
  screenshotFiles,
  setScreenshotFiles,
  submitPending,
  submitError,
  uploadProgress,
  website,
  onWebsiteChange,
  onSubmit,
}: PrintDetailsFormProps) {
  const noAvailablePools = poolsQuery.isSuccess && (poolsQuery.data?.length ?? 0) === 0;
  return (
    <Card>
      <h2 className="title-panel text-brand-ink">
        {t`Print details`}</h2>
      <form className="mt-4 space-y-4" onSubmit={onSubmit}>
        {/* Honeypot: hidden from humans; bots that autofill it trigger the server decoy. */}
        <input
          aria-hidden="true"
          autoComplete="off"
          className="hidden"
          name="website"
          tabIndex={-1}
          value={website}
          onChange={(event) => onWebsiteChange(event.target.value)}
        />
        <fieldset className="space-y-4" disabled={submitPending}><legend className="title-section mb-4">{t`Your print`}</legend>
          <TextInput
            label={t`Title`}
            required
            value={form.title}
            onChange={(value) => updateField("title", value)}
          />
          <TextArea
            label={t`Project brief`}
            value={form.projectBrief}
            onChange={(value) => updateField("projectBrief", value)}
          />
          <TextArea
            label={t`Slicer settings / personal preferences`}
            value={form.preferredSettings}
            onChange={(value) => updateField("preferredSettings", value)}
          />
        </fieldset>
        <fieldset className="space-y-4" disabled={submitPending}><legend className="title-section mb-4">{t`Material`}</legend>
          {catalogue?.materials.length ? <div className="grid gap-3 md:grid-cols-2">
            <label className="grid gap-1 text-sm">{t`Material`}<select className="desk-input w-full" value={form.material} onChange={event => { updateField("material", event.target.value); updateField("color", ""); updateField("consumablePoolId", ""); }}><option value="">{t`No preference`}</option>{catalogue.materials.map(material => <option key={material.name}>{material.name}</option>)}</select></label>
            <label className="grid gap-1 text-sm">{t`Colour`}<select className="desk-input w-full" value={form.color} required={Boolean(form.material)} onChange={event => updateField("color", event.target.value)}><option value="">{t`Choose a colour`}</option>{catalogue.materials.find(m => m.name === form.material)?.colours.map(c => <option key={c}>{c}</option>)}</select></label>
          </div> : null}
          <div className="grid gap-4 md:grid-cols-2">
            {noAvailablePools ? (
              <div>
                <span className="mb-1 block text-sm font-semibold text-ink">{t`Filament / material`}</span>
                <EmptyState
                  title={t`No filament currently available`}
                  description={t`There is no filament available to choose right now. You can still submit without a preference, and staff will confirm the options.`}
                />
              </div>
            ) : (
              <label className="block">
                <span className="mb-1 block text-sm font-semibold text-ink">
                  {t`Filament / material`}</span>
                <select
                  className="desk-input w-full"
                  value={form.consumablePoolId}
                  onChange={(event) => {
                    updateField("consumablePoolId", event.target.value);
                    const pool = poolsQuery.data?.find(row => String(row.id) === event.target.value);
                    if (pool) { updateField("material", pool.material); updateField("color", pool.color); }
                  }}
                >
                  <option value="">{t`No preference`}</option>
                  {groupPoolsByMaterial(poolsQuery.data ?? []).map(([material, pools]) => (
                    <optgroup key={material} label={material}>
                      {pools.map((pool) => (
                        <option key={pool.id} value={pool.id}>
                          {pool.color || t`Default color`}
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                {poolsQuery.isLoading ? (
                  <p className="mt-1 text-sm text-muted">{t`Loading filament…`}</p>
                ) : null}
                {poolsQuery.isError ? (
                  <p className="mt-1 text-sm text-danger">
                    {poolsQuery.error.message}
                  </p>
                ) : null}
              </label>
            )}
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-ink">
                {t`Quantity`}</span>
              <input
                className="desk-input w-full tabular-nums"
                min={1}
                type="number"
                value={form.quantity}
                onChange={(event) =>
                  updateField("quantity", Math.max(1, Number(event.target.value) || 1))
                }
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm font-semibold text-ink">
                {t`Estimated filament (g) — optional`}</span>
              <input
                className="desk-input w-full tabular-nums"
                min={0}
                step="0.01"
                type="number"
                value={form.estimatedFilamentGrams}
                onChange={(event) =>
                  updateField("estimatedFilamentGrams", event.target.value)
                }
              />
              <span className="mt-1 block text-sm text-muted">
                {t`If you know it from your slicer — staff can adjust this.`}</span>
            </label>
            <TextInput label={t`Source link (optional)`} value={form.sourceLink} onChange={(value) => updateField("sourceLink", value)} />
          </div>
        </fieldset>
        <fieldset className="space-y-4" disabled={submitPending}><legend className="title-section mb-4">{t`Files`}</legend>
          <div className="grid gap-4 md:grid-cols-2">
            <FilePicker
              accept=".stl,.3mf,.step,.stp,.obj,.amf,.ply,.gcode,.gco,.iges,.igs,.dxf"
              files={modelFiles}
              label={t`Model, CAD, or toolpath files`}
              setFiles={setModelFiles}
            />
            <FilePicker
              accept="image/*,application/pdf"
              files={screenshotFiles}
              label={t`Estimated print-time screenshots (Bambu Lab)`}
              setFiles={setScreenshotFiles}
            />
          </div>
        </fieldset>

        {uploadProgress ? <p className="text-sm text-muted">{uploadProgress}</p> : null}
        {submitError ? (
          <p className="rounded-lg border border-danger-line bg-panel px-3 py-2 text-sm text-danger">
            {submitError.message}
          </p>
        ) : null}
        <button
          className="desk-button-brand w-full disabled:cursor-not-allowed"
          disabled={
            !form.title.trim() ||
            submitPending
          }
          type="submit"
        >
          {submitPending ? t`Sending…` : t`Send print request`}
        </button>
      </form>
    </Card>
  );
}
