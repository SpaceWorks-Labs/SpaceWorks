import { t } from "@lingui/core/macro";
import { useMutation, useQuery } from "@tanstack/react-query";

import { BoxArt } from "../../../components/BoxSpinner";
import { adapterErrorMessage } from "../panels/machine/adapters/adapterCopy";
import { isShelfOff, shelfApi, shelfKeys, type ShelfTargetType } from "./shelfApi";

/** True when a calibrated pointer covers this target. A space without the pointer (404) or a person without access (403) is just "no". */
export function useShelfCovered(makerspaceId: number, targetType: ShelfTargetType, targetId: string | number, enabled = true) {
  const id = String(targetId);
  const coverage = useQuery({
    queryKey: shelfKeys.coverage(makerspaceId, targetType, id), enabled: enabled && Boolean(makerspaceId) && id !== "", retry: false, staleTime: 30_000,
    queryFn: async () => {
      try { return (await shelfApi.coverage(makerspaceId, [{ target_type: targetType, target_id: id }])).results[0]?.covered ?? false; }
      catch (error) { if (isShelfOff(error)) return false; throw error; }
    },
  });
  return coverage.data === true;
}

type Props = { makerspaceId: number; targetType: ShelfTargetType; targetId: string | number; label?: string;
  /** The caller already knows the answer (a list that fetched coverage once): skip the per-target request. */
  covered?: boolean };

/** "Show on shelf" and "Clear": appears only when a calibrated shelf pointer covers the target. Staff only; the position never reaches this screen. */
export function ShowOnShelf({ makerspaceId, targetType, targetId, label, covered }: Props) {
  const lookedUp = useShelfCovered(makerspaceId, targetType, targetId, covered === undefined);
  const target = { target_type: targetType, target_id: String(targetId) };
  const show = useMutation({ mutationFn: () => shelfApi.show(makerspaceId, target) });
  const clear = useMutation({ mutationFn: () => shelfApi.clear(makerspaceId, target), onSuccess: () => show.reset() });
  if (!(covered ?? lookedUp)) return null;
  const error = show.error ?? clear.error;
  return <div className="flex flex-wrap items-center gap-2" role="group" aria-label={label ?? t`Shelf pointer`}>
    <button type="button" className="desk-button" disabled={show.isPending} onClick={() => show.mutate()}>
      {show.isPending ? <><BoxArt size={16} mono />{t`Pointing…`}</> : t`Show on shelf`}</button>
    <button type="button" className="desk-button-ghost" disabled={clear.isPending} onClick={() => clear.mutate()}>
      {clear.isPending ? <><BoxArt size={16} mono />{t`Clearing…`}</> : t`Clear`}</button>
    {show.isSuccess ? <span role="status" className="text-xs text-muted">{t`Pointer sent.`}</span> : null}
    {error ? <span role="alert" className="text-xs text-danger">{adapterErrorMessage(error)}</span> : null}
  </div>;
}
