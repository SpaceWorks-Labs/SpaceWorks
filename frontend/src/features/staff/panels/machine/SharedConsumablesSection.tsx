import { t } from "@lingui/core/macro";
import { useState, type Dispatch, type SetStateAction } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge, CollapsibleSection, ErrorBlock } from "../../../../components/ui";
import type { PrinterPool } from "../../../../generated/api";
import { staffRequest } from "../../../../lib/api";
import { blankPool, ConsumablePoolCreateForm } from "./ConsumablePoolCreateForm";
import { poolLabel, poolQueryKey } from "./servicePools";
import { PriceOverrideCard } from "../../pricing/PriceOverrideCard";

type Props = {
  visible?: boolean;
  makerspaceId: number;
  pools: PrinterPool[];
  existingPools: PrinterPool[];
  poolError: unknown;
  open: boolean;
  onToggle: () => void;
};

type StockState = {
  label: string;
  band: string;
  fill: string;
};

export function poolStockState(pool: PrinterPool): StockState {
  const remaining = Number(pool.remaining_grams);
  const threshold = pool.low_threshold_grams === null || pool.low_threshold_grams === undefined
    ? null
    : Number(pool.low_threshold_grams);
  if (remaining <= 0) {
    return { label: t`Empty`, band: "bg-danger text-on-danger", fill: "bg-danger" };
  }
  if (threshold !== null && remaining <= threshold) {
    return { label: t`Low stock`, band: "bg-warn text-on-warn", fill: "bg-warn" };
  }
  return { label: t`In stock`, band: "bg-success text-on-success", fill: "bg-success" };
}

export function SharedConsumablesSection({ makerspaceId, pools, existingPools, poolError, open, onToggle, visible = true }: Props) {
  const [poolDraft, setPoolDraft] = useState(blankPool);
  const [stockDraft, setStockDraft] = useState<StockDraft>({ adjustingId: null, quantityDelta: "" });
  if (!visible) return null;
  return (
    <CollapsibleSection title={t`Shared consumables`} count={pools.length} open={open} onToggle={onToggle}>
      <div className="grid gap-4 p-3">
        <ConsumablePoolCreateForm makerspaceId={makerspaceId} existingPools={existingPools} draft={poolDraft} onDraftChange={setPoolDraft} />
        <section>
          <h4 className="title-section mb-2">{t`Space-wide stock`}</h4>
          <ConsumablePoolList makerspaceId={makerspaceId} pools={pools} draft={stockDraft} onDraftChange={setStockDraft} />
        </section>
        <ErrorBlock className="mt-2" error={poolError} />
      </div>
    </CollapsibleSection>
  );
}

type StockDraft = { adjustingId: number | null; quantityDelta: string };
export function ConsumablePoolList({ makerspaceId, pools, visible = true, draft, onDraftChange }: { makerspaceId: number; pools: PrinterPool[]; visible?: boolean; draft?: StockDraft; onDraftChange?: Dispatch<SetStateAction<StockDraft>> }) {
  const queryClient = useQueryClient();
  const [localDraft, setLocalDraft] = useState<StockDraft>({ adjustingId: null, quantityDelta: "" });
  const { adjustingId, quantityDelta } = draft ?? localDraft;
  const changeDraft = onDraftChange ?? setLocalDraft;
  const setAdjustingId = (value: number | null) => changeDraft(current => ({ ...current, adjustingId: value }));
  const setQuantityDelta = (value: string) => changeDraft(current => ({ ...current, quantityDelta: value }));
  const refresh = () => queryClient.invalidateQueries({ queryKey: poolQueryKey(makerspaceId) });
  const adjustPool = useMutation({
    mutationFn: ({ id, quantity_delta }: { id: number; quantity_delta: string }) => staffRequest(`/admin/machine-service/consumable-pools/${id}/adjustments`, {
      method: "POST",
      body: JSON.stringify({ quantity_delta, reason: t`Manual correction` }),
    }),
    onSuccess: async () => {
      setAdjustingId(null);
      setQuantityDelta("");
      await refresh();
    },
  });
  const visibility = useMutation({
    mutationFn: ({ id, isPublic }: { id: number; isPublic: boolean }) => staffRequest<PrinterPool>(`/admin/machine-service/consumable-pools/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_public: isPublic }),
    }),
    onSuccess: refresh,
  });

  if (!visible) return null;
  return (
    <>
      <div className="grid gap-3">
        {pools.map((pool) => {
          const label = poolLabel(pool);
          const unit = pool.unit ?? "grams";
          const initial = Number(pool.initial_grams);
          const remaining = Number(pool.remaining_grams);
          const percent = initial > 0 ? Math.max(0, Math.min(100, (remaining / initial) * 100)) : 0;
          const state = poolStockState(pool);
          const isPublic = pool.is_public !== false;
          const isAdjusting = adjustingId === pool.id;
          const validAdjustment = quantityDelta.trim() !== "" && Number.isFinite(Number(quantityDelta)) && Number(quantityDelta) !== 0;
          return (
            <article className="overflow-hidden rounded-xl border border-line bg-bg" key={pool.id}>
              <div className={`flex items-center justify-between gap-2 px-3 py-1.5 tabular-nums text-xs font-semibold ${state.band}`}>
                <span>{state.label}</span>
                <span>{t`${Math.round(percent)}% remaining`}</span>
              </div>
              <div className="grid gap-3 p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0 break-words">
                    <strong className="text-sm text-ink">{label}</strong>
                    <div className="mt-1 flex flex-wrap gap-2">
                      <Badge tone={pool.machine_id !== null ? "emphasis" : pool.machine_type_id !== null ? "accent" : "neutral"}>
                        {pool.machine_id !== null ? t`Machine-specific` : pool.machine_type_id !== null ? t`Type-wide` : t`Space-wide`}
                      </Badge>
                      <span className="chip">
                        <span
                          aria-hidden="true"
                          className="h-3 w-3 rounded-full border border-outline bg-surface"
                          style={pool.color_hex || pool.color ? { backgroundColor: pool.color_hex || pool.color } : undefined}
                        />
                        {t`Colour: `}{pool.color || t`Not specified`}
                      </span>
                      {!isPublic ? <Badge tone="warn">{t`Hidden from requesters`}</Badge> : null}
                    </div>
                  </div>
                  {/* The accessible name must START with the visible text, or voice control cannot
                      act on what the user reads (WCAG 2.5.3 Label in Name) -- "click Public" has to
                      match. State lives in the label rather than aria-pressed: carrying both a
                      changing name and a pressed state double-signals the same fact. */}
                  <button
                    aria-label={t`${isPublic ? "Public" : "Hidden"}: ${label} — activate to ${isPublic ? "hide from" : "show to"} requesters`}
                    className={isPublic ? "desk-button-warn" : "desk-button-success"}
                    disabled={visibility.isPending}
                    type="button"
                    onClick={() => visibility.mutate({ id: pool.id, isPublic: !isPublic })}
                  >
                    {isPublic ? t`Public` : t`Hidden`}
                  </button>
                </div>
                <div>
                  <div
                    aria-label={`${label} remaining`}
                    aria-valuemax={initial}
                    aria-valuemin={0}
                    aria-valuenow={remaining}
                    className="h-3 overflow-hidden rounded-full bg-surface"
                    role="progressbar"
                  >
                    <div className={`h-full rounded-full ${state.fill}`} style={{ width: `${percent}%` }} />
                  </div>
                  <p className="mt-1 tabular-nums text-sm text-muted">
                    <strong className="text-ink">{pool.remaining_grams}</strong> / {pool.initial_grams} {unit}
                  </p>
                </div>
                {isAdjusting ? (
                  <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); if (validAdjustment) adjustPool.mutate({ id: pool.id, quantity_delta: quantityDelta }); }}>
                    <label className="eyebrow grid min-w-48 flex-1 gap-1">
                      {t`Adjustment (${unit}, + or −)`}<input
                        autoFocus
                        className="desk-input"
                        inputMode="decimal"
                        step="any"
                        type="number"
                        value={quantityDelta}
                        onChange={(event) => setQuantityDelta(event.target.value)}
                        required
                      />
                    </label>
                    <button className="desk-button-primary" disabled={!validAdjustment || adjustPool.isPending} type="submit">
                      {adjustPool.isPending ? t`Saving...` : t`Save adjustment`}
                    </button>
                    <button className="desk-button-ghost" disabled={adjustPool.isPending} type="button" onClick={() => { setAdjustingId(null); setQuantityDelta(""); adjustPool.reset(); }}>
                      {t`Cancel`}</button>
                  </form>
                ) : (
                  <button className="desk-button justify-self-start" type="button" onClick={() => { setAdjustingId(pool.id); setQuantityDelta(""); adjustPool.reset(); }}>
                    {t`Adjust stock`}</button>
                )}
                <PriceOverrideCard makerspaceId={makerspaceId} targetType="consumable_pool" targetId={pool.id} compact />
              </div>
            </article>
          );
        })}
        {!pools.length ? <p className="text-sm text-muted">{t`No consumable pools.`}</p> : null}
      </div>
      <ErrorBlock className="mt-2" error={adjustPool.error ?? visibility.error} />
    </>
  );
}
