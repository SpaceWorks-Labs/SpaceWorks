import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { EmptyState, ListRow, StatusPill } from "../../../components/ui";
import { StructuredApiError, staffRequestBlob } from "../../../lib/api";
import { STANDING_LABELS, lifecycleApi, lifecycleKeys, standingTone, type Standing } from "../membershipLifecycleApi";

const FILTERS: Standing[] = ["active", "ending_soon", "grace", "lapsed", "upcoming", "no_term"];
const errorText = (error: unknown) => (error instanceof StructuredApiError ? error.message : t`Couldn't load the register.`);

/** X14: the register filtered by standing, and the CSV export through the report registry. */
export function MemberRegisterList({ makerspaceId, initialStanding = "" }: { makerspaceId: number; initialStanding?: string }) {
  const [standing, setStanding] = useState(initialStanding);
  const register = useQuery({ queryKey: lifecycleKeys.register(makerspaceId, standing), queryFn: () => lifecycleApi.register(makerspaceId, standing) });
  const exportCsv = useMutation({
    mutationFn: () => staffRequestBlob(`/admin/makerspace/${makerspaceId}/reports/member-register/export?format=csv`),
    onSuccess: (blob) => {
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "member-register.csv";
      link.click();
      URL.revokeObjectURL(link.href);
    },
  });
  const rows = register.data ?? [];
  return <section aria-label={t`Member register`} className="grid gap-3">
    <div className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1 text-sm">{t`Standing`}<select className="desk-input max-w-full" value={standing} onChange={(event) => setStanding(event.target.value)}>
          <option value="">{t`Every standing`}</option>
          {FILTERS.map((value) => <option key={value} value={value}>{STANDING_LABELS[value]}</option>)}
        </select>
      </label>
      <button className="desk-button" type="button" disabled={exportCsv.isPending} onClick={() => exportCsv.mutate()}>
        {exportCsv.isPending ? t`Preparing…` : t`Export CSV`}
      </button>
    </div>
    {exportCsv.error ? <p role="alert" className="text-sm text-danger">{errorText(exportCsv.error)}</p> : null}
    {register.isLoading ? <p className="text-sm text-muted">{t`Loading the register…`}</p> : null}
    {register.isError ? <p role="alert" className="text-sm text-danger">{errorText(register.error)}</p> : null}
    {register.isSuccess && !rows.length ? <EmptyState message={t`No members with this standing.`} /> : null}
    {rows.map((row, index) => <ListRow key={`${row.member_number}-${index}`} title={row.name || row.email}
      identity={{ kind: "avatar", name: row.name || row.email, seed: row.member_number || String(index) }}
      meta={<>{row.member_number ? `${row.member_number} · ` : ""}{row.plan || t`No plan`}{row.term_ends_at ? t` · ends ${new Date(row.term_ends_at).toLocaleDateString(formatLocale())}` : ""}</>}
      right={<StatusPill tone={standingTone(row.standing)} label={STANDING_LABELS[row.standing] ?? row.standing} />} />)}
  </section>;
}
