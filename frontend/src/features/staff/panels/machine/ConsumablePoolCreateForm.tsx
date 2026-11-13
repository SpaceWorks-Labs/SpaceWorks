import { t } from "@lingui/core/macro";
import { useId, useMemo, useState, type Dispatch, type SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { PrinterPool } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { isBuiltinPrinterType, type MachineType } from "../../machinesApi";
import { PoolColourSelector } from "./PoolColourSelector";
import { poolPath, poolQueryKey, type PoolUnit } from "./servicePools";
import { BoxArt } from "../../../../components/BoxSpinner";

type Props = {
  visible?: boolean;
  draft?: PoolDraft;
  onDraftChange?: Dispatch<SetStateAction<PoolDraft>>;
  makerspaceId: number;
  machineType?: MachineType;
  existingPools: PrinterPool[];
};

export type PoolDraft = {
  material: string;
  color: string;
  colorHex: string;
  brand: string;
  quantity: string;
  unit: PoolUnit;
  lowThreshold: string;
  isPublic: boolean;
};

export const blankPool = (): PoolDraft => ({
  material: "",
  color: "",
  colorHex: "",
  brand: "",
  quantity: "",
  unit: "grams",
  lowThreshold: "",
  isPublic: true,
});

export function ConsumablePoolCreateForm({ makerspaceId, machineType, existingPools, visible = true, draft, onDraftChange }: Props) {
  const queryClient = useQueryClient();
  const brandListId = useId();
  const [localPool, setLocalPool] = useState(blankPool);
  const pool = draft ?? localPool;
  const setPool = onDraftChange ?? setLocalPool;
  const printerType = isBuiltinPrinterType(machineType);
  const materialPresets = machineType?.capability_config?.accepted_materials;
  const brands = useMemo(() => {
    const used = new Map<string, string>();
    existingPools.forEach(({ brand }) => {
      const trimmed = brand?.trim();
      if (trimmed && !used.has(trimmed.toLocaleLowerCase())) used.set(trimmed.toLocaleLowerCase(), trimmed);
    });
    return [...used.values()].sort((left, right) => left.localeCompare(right));
  }, [existingPools]);
  const createPool = useMutation({
    mutationFn: () => staffRequest<PrinterPool>(poolPath(makerspaceId), {
      method: "POST",
      body: JSON.stringify({
        machine_type_id: machineType?.id ?? null,
        is_public: pool.isPublic,
        material: pool.material.trim(),
        color: pool.color.trim(),
        color_hex: pool.colorHex,
        brand: pool.brand.trim(),
        quantity: pool.quantity,
        unit: pool.unit,
        low_threshold_grams: pool.unit === "grams" && pool.lowThreshold ? pool.lowThreshold : null,
      }),
    }),
    onSuccess: async () => {
      setPool(blankPool());
      await queryClient.invalidateQueries({ queryKey: poolQueryKey(makerspaceId) });
    },
  });

  const scopeCopy = machineType
    ? `Type-wide — available to every ${machineType.name} machine.`
    : "Space-wide — available to every compatible machine in this makerspace.";

  if (!visible) return null;
  return (
    <form className="grid gap-3" onSubmit={(event) => { event.preventDefault(); createPool.mutate(); }}>
      <div>
        <h4 className="title-section">{printerType ? t`Add filament` : t`Create consumable pool`}</h4>
        <p className="mt-1 text-sm text-muted"><span className="eyebrow mr-2">{t`Scope`}</span>{scopeCopy}</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        <label className="eyebrow grid gap-1">
          {t`Material`}{materialPresets ? (
            <select className="desk-input" value={pool.material} onChange={(event) => setPool({ ...pool, material: event.target.value })} required>
              <option value="">{t`Select material`}</option>
              {materialPresets.map((material) => <option key={material} value={material}>{material}</option>)}
            </select>
          ) : (
            <input className="desk-input" value={pool.material} onChange={(event) => setPool({ ...pool, material: event.target.value })} required />
          )}
        </label>
        <label className="eyebrow grid gap-1">
          {t`Brand`}<input className="desk-input" list={brandListId} value={pool.brand} onChange={(event) => setPool({ ...pool, brand: event.target.value })} />
          <datalist id={brandListId}>{brands.map((brand) => <option key={brand} value={brand} />)}</datalist>
        </label>
        {printerType ? (
          <div>
            <span className="eyebrow block">{t`Unit`}</span>
            <p className="flex min-h-11 items-center text-sm text-ink">{t`Grams`}</p>
          </div>
        ) : (
          <label className="eyebrow grid gap-1">
            {t`Unit`}<select className="desk-input" value={pool.unit} onChange={(event) => setPool({ ...pool, unit: event.target.value as PoolUnit })}>
              <option value="grams">{t`Grams`}</option>
              <option value="milliliters">{t`Milliliters`}</option>
              <option value="millimeters">{t`Millimeters`}</option>
              <option value="count">{t`Count`}</option>
            </select>
          </label>
        )}
        <label className="eyebrow grid gap-1">
          {t`Initial quantity`}<input className="desk-input" type="number" min="0" step="any" value={pool.quantity} onChange={(event) => setPool({ ...pool, quantity: event.target.value })} required />
        </label>
        {pool.unit === "grams" ? (
          <label className="eyebrow grid gap-1">
            {t`Low threshold (grams)`}<input className="desk-input" type="number" min="0" step="any" value={pool.lowThreshold} onChange={(event) => setPool({ ...pool, lowThreshold: event.target.value })} />
          </label>
        ) : null}
      </div>
      <PoolColourSelector
        makerspaceId={makerspaceId}
        machineType={machineType}
        existingPools={existingPools}
        value={pool.color}
        valueHex={pool.colorHex}
        onSelect={(color, colorHex) => setPool((current) => ({ ...current, color, colorHex }))}
      />
      <div className="flex flex-wrap items-center gap-2">
        <button
          aria-pressed={pool.isPublic}
          className={pool.isPublic ? "desk-button-success" : "desk-button-warn"}
          type="button"
          onClick={() => setPool({ ...pool, isPublic: !pool.isPublic })}
        >
          {pool.isPublic ? t`Visible to requesters` : t`Hidden from requesters`}
        </button>
        <button className="desk-button-primary" disabled={!pool.material.trim() || !pool.quantity || createPool.isPending} type="submit">
          {createPool.isPending ? <><BoxArt size={16} mono />{t`Adding...`}</> : printerType ? t`Add filament` : t`Add pool`}
        </button>
      </div>
      {createPool.error instanceof Error ? <p className="text-sm text-danger">{createPool.error.message}</p> : null}
    </form>
  );
}
