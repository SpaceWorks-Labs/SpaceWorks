import { t } from "@lingui/core/macro";
import { ListRow, StatusPill, OverflowMenu } from "../../../../components/ui";
import { MachineTabContent } from "./MachineTabContent";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  getConsumableCandidates,
  getMachineConsumables,
  linkMachineConsumable,
  logMachineConsumption,
  machineKeys,
  unlinkMachineConsumable,
  type ConsumableMeasurement,
  type MachineConsumable,
} from "../../machinesApi";

export function ConsumablesTab({ machineId, canEdit, canOperate }: {
  machineId: number;
  canEdit: boolean;
  canOperate: boolean;
}) {
  const queryClient = useQueryClient();
  const [measurement, setMeasurement] = useState<ConsumableMeasurement>("count");
  const [productId, setProductId] = useState("");
  const [label, setLabel] = useState("");
  const [remaining, setRemaining] = useState("");
  const [lowThreshold, setLowThreshold] = useState("");
  const [note, setNote] = useState("");
  const consumables = useQuery({
    queryKey: machineKeys.consumables(machineId),
    queryFn: () => getMachineConsumables(machineId),
  });
  const candidates = useQuery({
    queryKey: machineKeys.consumableCandidates(machineId),
    queryFn: () => getConsumableCandidates(machineId),
    enabled: canEdit,
  });
  const items = consumables.data ?? [];
  const linkedProducts = new Set(items.flatMap((item) => item.product ? [item.product] : []));
  const eligible = (candidates.data ?? []).filter((item) => !linkedProducts.has(item.id));
  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: machineKeys.consumables(machineId) }),
    queryClient.invalidateQueries({ queryKey: machineKeys.consumableCandidates(machineId) }),
  ]);
  const link = useMutation({
    mutationFn: () => linkMachineConsumable(machineId, measurement === "count" ? {
      measurement,
      product_id: Number(productId),
      low_threshold: lowThreshold || null,
      note: note.trim(),
    } : {
      measurement,
      label: label.trim(),
      remaining: remaining || "0",
      low_threshold: lowThreshold || null,
      note: note.trim(),
    }),
    onSuccess: async () => {
      setProductId(""); setLabel(""); setRemaining(""); setLowThreshold(""); setNote("");
      await refresh();
    },
  });
  const unlink = useMutation({
    mutationFn: (id: number) => unlinkMachineConsumable(machineId, id),
    onSuccess: refresh,
  });

  return (
    <section className="grid gap-3">
      <h3 className="title-section">{t`Consumables`}</h3>
      <MachineTabContent query={consumables} resource={t`consumables`} empty={!items.length} message={t`No consumables linked. Add the first consumable.`}>
      <div className="grid gap-2">
        {items.map((item) => (
          <ConsumableRow key={item.id} item={item} machineId={machineId} canOperate={canOperate}
            canEdit={canEdit} removing={unlink.isPending} onRemove={() => unlink.mutate(item.id)}
            onLogged={refresh} />
        ))}
      </div>
      </MachineTabContent>
      {canEdit ? (
        <form className="grid gap-2 rounded-md border border-line bg-bg p-3"
          onSubmit={(event) => { event.preventDefault(); link.mutate(); }}>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="eyebrow grid gap-1">{t`Measurement`}<select className="desk-input" value={measurement}
                onChange={(event) => setMeasurement(event.target.value as ConsumableMeasurement)}>
                <option value="count">{t`Count (inventory)`}</option>
                <option value="grams">{t`Grams (local ledger)`}</option>
              </select>
            </label>
            {measurement === "count" ? (
              <label className="eyebrow grid gap-1">{t`Inventory product`}<select className="desk-input" value={productId} onChange={(event) => setProductId(event.target.value)} required>
                  <option value="">{t`Select a product`}</option>
                  {eligible.map((item) => <option key={item.id} value={item.id}>{item.name} ({item.available} available)</option>)}
                </select>
              </label>
            ) : (
              <label className="eyebrow grid gap-1">{t`Label`}<input className="desk-input" maxLength={200} value={label}
                  onChange={(event) => setLabel(event.target.value)} required />
              </label>
            )}
            {measurement === "grams" ? (
              <label className="eyebrow grid gap-1">{t`Starting grams`}<input className="desk-input" type="number" min="0" step="0.01" value={remaining}
                  onChange={(event) => setRemaining(event.target.value)} />
              </label>
            ) : null}
            <label className="eyebrow grid gap-1">{t`Low threshold (${measurement})`}<input className="desk-input" type="number" min="0" step={measurement === "count" ? "1" : "0.01"}
                value={lowThreshold} onChange={(event) => setLowThreshold(event.target.value)} />
            </label>
          </div>
          <label className="eyebrow grid gap-1">{t`Note`}<input className="desk-input" maxLength={255} value={note} onChange={(event) => setNote(event.target.value)} />
          </label>
          <button className="desk-button-primary justify-self-start" type="submit"
            disabled={link.isPending || (measurement === "count" ? !productId : !label.trim())}>
            {link.isPending ? t`Linking...` : measurement === "count" ? t`Link product` : t`Add grams consumable`}
          </button>
        </form>
      ) : null}
      {[link.error, unlink.error].map((error, index) => error instanceof Error
        ? <p key={index} role="alert" className="text-sm text-danger">{error.message}</p> : null)}
    </section>
  );
}

function ConsumableRow({ item, machineId, canOperate, canEdit, removing, onRemove, onLogged }: {
  item: MachineConsumable;
  machineId: number;
  canOperate: boolean;
  canEdit: boolean;
  removing: boolean;
  onRemove: () => void;
  onLogged: () => Promise<unknown>;
}) {
  const [quantity, setQuantity] = useState("");
  const balance = item.measurement === "count" ? item.available : Number(item.remaining);
  const threshold = item.low_threshold === null ? null : Number(item.low_threshold);
  const isLow = threshold !== null && balance !== null && Number(balance) <= threshold;
  const log = useMutation({
    mutationFn: () => logMachineConsumption(machineId, item.id, quantity),
    onSuccess: async () => { setQuantity(""); await onLogged(); },
  });

  return (
    <div className="grid gap-3">
      <ListRow title={item.product_name ?? item.label} meta={<>{item.measurement === "count" ? `${item.available ?? 0} available` : t`${item.remaining ?? "0.00"} g remaining`}{item.note ? <span className="block">{item.note}</span> : null}</>}
        right={<div className="flex flex-wrap gap-2">{isLow ? <StatusPill label={t`Low`} tone="warn" /> : null}{canEdit ? <OverflowMenu actions={[{ label: t`Unlink`, tone: "danger", disabled: removing, disabledReason: t`Wait for the current change to finish.`, onClick: onRemove }]} /> : null}</div>} />
      {canOperate ? (
        <form className="mt-2 flex flex-wrap items-end gap-2" onSubmit={(event) => { event.preventDefault(); log.mutate(); }}>
          <label className="eyebrow grid gap-1">{t`Use (${item.measurement})`}<input className="desk-input w-32" type="number" min={item.measurement === "count" ? "1" : "0.01"}
              step={item.measurement === "count" ? "1" : "0.01"} value={quantity}
              onChange={(event) => setQuantity(event.target.value)} required />
          </label>
          <button className="desk-button-primary" type="submit" disabled={log.isPending || !quantity}>
            {log.isPending ? t`Logging...` : t`Log consumption`}
          </button>
        </form>
      ) : null}
      {log.error instanceof Error ? <p role="alert" className="mt-2 text-sm text-danger">{log.error.message}</p> : null}
    </div>
  );
}
