import { t } from "@lingui/core/macro";
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { BoxArt } from "../../../components/BoxSpinner";
import { StatusPill } from "../../../components/ui";
import { adapterErrorMessage } from "../panels/machine/adapters/adapterCopy";
import { isShelfOff, shelfApi, shelfKeys } from "./shelfApi";

export type GuideProduct = { id: number; name: string; storage_location?: string };

/**
 * "Guide with the pointer": steps through the storage locations in shelf order, pointing at the first one that still has
 * something uncounted, and moves on by itself as counts are saved. A location with no calibrated pose is flagged so staff
 * find it by eye. Hidden entirely when the space has no shelf pointer (the locations route answers 404).
 */
export function StocktakeShelfGuide({ makerspaceId, products, counted }: { makerspaceId: number; products: GuideProduct[]; counted: Set<number> }) {
  const [on, setOn] = useState(false);
  const [skipped, setSkipped] = useState<string[]>([]);
  const locations = useQuery({ queryKey: shelfKeys.locations(makerspaceId, ""), retry: false, staleTime: 30_000,
    queryFn: async () => { try { return await shelfApi.locations(makerspaceId, ""); } catch (error) { if (isShelfOff(error)) return null; throw error; } } });
  const point = useMutation({ mutationFn: (location: string) => shelfApi.show(makerspaceId, { target_type: "storage_location", target_id: location }) });
  const clear = useMutation({ mutationFn: () => shelfApi.clear(makerspaceId) });
  const order = useMemo(() => {
    const byLocation = new Map<string, GuideProduct[]>();
    products.forEach(product => { if (product.storage_location) byLocation.set(product.storage_location, [...(byLocation.get(product.storage_location) ?? []), product]); });
    return [...byLocation.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([location, rows]) => ({ location, rows }));
  }, [products]);
  const covered = new Set((locations.data ?? []).filter(row => row.covered).map(row => row.location));
  const left = order.filter(step => !skipped.includes(step.location) && step.rows.some(row => !counted.has(row.id)));
  const step = left[0];
  const stepLocation = on ? step?.location : undefined;
  useEffect(() => { if (stepLocation && covered.has(stepLocation)) point.mutate(stepLocation); }, [stepLocation]); // eslint-disable-line react-hooks/exhaustive-deps -- points once per shelf step; `covered` and `point` are new each render and would re-point the same location
  if (!locations.data || !order.length) return null;
  const stop = () => { setOn(false); setSkipped([]); clear.mutate(); };
  const error = point.error ?? clear.error;
  return <section aria-label={t`Guide with the pointer`} className="mb-3 grid gap-2 rounded-md border border-line p-3">
    {!on ? <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-sm text-muted">{t`Let the shelf pointer lead you from shelf to shelf, in order.`}</p>
      <button type="button" className="desk-button" onClick={() => setOn(true)}>{t`Guide with the pointer`}</button></div>
      : step ? <>
        <div className="flex flex-wrap items-center gap-2"><strong className="text-ink">{step.location}</strong>
          <span className="text-sm text-muted">{t`${step.rows.filter(row => !counted.has(row.id)).length} to count · ${order.length - left.length + 1} of ${order.length}`}</span>
          {covered.has(step.location) ? <StatusPill tone="success" label={t`Pointer is on it`} /> : <StatusPill tone="warn" label={t`No pointer position saved - find it by eye`} />}</div>
        <p className="text-sm text-muted">{step.rows.filter(row => !counted.has(row.id)).map(row => row.name).join(", ")}</p>
        <div className="flex flex-wrap gap-2">
          {covered.has(step.location) ? <button type="button" className="desk-button" disabled={point.isPending} onClick={() => point.mutate(step.location)}>{point.isPending ? <><BoxArt size={16} mono />{t`Pointing…`}</> : t`Point again`}</button> : null}
          <button type="button" className="desk-button-ghost" onClick={() => setSkipped([...skipped, step.location])}>{t`Skip this shelf`}</button>
          <button type="button" className="desk-button-ghost" disabled={clear.isPending} onClick={stop}>{t`Stop guiding`}</button></div></>
        : <div className="flex flex-wrap items-center justify-between gap-2"><p role="status" className="text-sm text-ink">{t`Every shelf has been counted or skipped.`}</p>
          <button type="button" className="desk-button" onClick={stop}>{t`Finish`}</button></div>}
    {error ? <p role="alert" className="text-xs text-danger">{adapterErrorMessage(error)}</p> : null}
  </section>;
}
