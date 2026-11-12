import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { EmptyState, ErrorText, ListRow } from "../../../components/ui";
import { isSurfaceOff } from "../../../lib/api";
import { formatLocale } from "../../../lib/format";
import { Panel } from "../panels/shared";
import { unitErrorText, unitKeys, unitsApi, useMemberUnits } from "./unitsApi";
import { LogoLoader } from "../../../components/LogoLoader";

/**
 * The unit lead's queue for imports run in verify mode: approve sends the normal invitation, reject
 * cancels the row and sends nothing. A unit-scoped lead sees only their own unit's rows; names and
 * emails arrive masked without a personal-data window.
 */
export function ImportReviewQueue({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const key = unitKeys.reviews(makerspaceId);
  const rows = useQuery({ queryKey: key, queryFn: () => unitsApi.reviews(makerspaceId), retry: false });
  const units = useMemberUnits(makerspaceId);
  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approve" | "reject" }) => unitsApi.decideReview(makerspaceId, id, decision),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: key });
      void client.invalidateQueries({ queryKey: ["membership-l4", makerspaceId, "imported"] });
    },
  });
  if (isSurfaceOff(rows.error)) return null;
  const unitName = (id: number) => units.data?.units.find(unit => unit.id === id)?.name ?? t`Unit #${id}`;
  return <Panel title={t`Import review`}>
    <p className="mb-3 text-sm text-muted">{t`Rows imported for a unit lead to check. Approving one sends that person the usual invitation; rejecting cancels it and sends nothing.`}</p>
    {rows.isPending ? <LogoLoader label={t`Loading rows…`} size={48} className="min-h-16 py-3" /> : null}
    {rows.isError ? <ErrorText message={unitErrorText(rows.error)} onRetry={() => void rows.refetch()} /> : null}
    {rows.isSuccess && !rows.data.length ? <EmptyState message={t`Nothing waiting for review.`} /> : null}
    <div className="grid gap-2">{rows.data?.map(row => {
      const pending = decide.isPending && decide.variables?.id === row.id;
      return <ListRow key={row.id} title={row.name} identity={{ kind: "avatar", name: row.name, seed: String(row.id) }}
        meta={<>{row.email} · {unitName(row.unit_id)} · {t`imported ${new Date(row.created_at).toLocaleDateString(formatLocale())}`}</>}
        right={<div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button-primary min-h-11" disabled={decide.isPending}
            onClick={() => decide.mutate({ id: row.id, decision: "approve" })}>{pending && decide.variables?.decision === "approve" ? t`Approving…` : t`Approve`}</button>
          <button type="button" className="desk-button-danger-outline min-h-11" disabled={decide.isPending}
            onClick={() => decide.mutate({ id: row.id, decision: "reject" })}>{pending && decide.variables?.decision === "reject" ? t`Rejecting…` : t`Reject`}</button>
        </div>} />;
    })}</div>
    {decide.error ? <div className="mt-2"><ErrorText message={unitErrorText(decide.error)} /></div> : null}
  </Panel>;
}
