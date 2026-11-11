import { t } from "@lingui/core/macro";
import { Clock } from "lucide-react";
import { useState } from "react";

import { formatDate } from "../../lib/format";
import { OrganizationHoursLedgerTable, minutesToHours } from "./OrganizationHoursLedgerTable";
import { useOwnOrganizationHours, useOwnOrganizationHoursLedger } from "./organizationHoursApi";
import { ErrorText, PagePager } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";

function LedgerPeek({ organizationId, makerspaceId }: { organizationId: number; makerspaceId: number }) {
  const [page, setPage] = useState(1);
  const ledger = useOwnOrganizationHoursLedger(organizationId, makerspaceId, page, true);
  if (ledger.isError) return <ErrorText resource={t`the hours ledger`} onRetry={() => { void ledger.refetch(); }} />;
  if (!ledger.data) return <p role="status" className="mt-2 text-sm text-muted">{t`Loading the hours ledger…`}</p>;
  return <div className="mt-2 grid gap-2">
    <OrganizationHoursLedgerTable rows={ledger.data.results} showActor={false} />
    <PagePager page={page} setPage={setPage} next={ledger.data.next} />
  </div>;
}

/**
 * Open item B13: the read-only hours balance an organization admin sees for their own organization, one line per
 * makerspace that gave it an allowance, with the ledger behind a disclosure. Renders nothing when there is none, or
 * when the server answers 404 (not an organization admin, decision 270). OR-13: other failures say so with a retry.
 */
export function OrganizationHoursBankBalance({ organizationId }: { organizationId: number }) {
  const banks = useOwnOrganizationHours(organizationId, true);
  if (banks.isLoading) return <p role="status" className="text-sm text-muted">{t`Loading hours balance…`}</p>;
  if (banks.isError) {
    if (banks.error instanceof StructuredApiError && banks.error.status === 404) return null;
    return <ErrorText resource={t`the hours balance`} onRetry={() => { void banks.refetch(); }} />;
  }
  if (!banks.data?.banks.length) return null;
  return <ul className="grid gap-3">{banks.data.banks.map(bank => {
    const left = minutesToHours(bank.remaining_minutes);
    const pool = minutesToHours(bank.pool_minutes);
    const space = bank.makerspace_name ?? "";
    return <li key={bank.makerspace_id} className="rounded-lg border border-line p-3">
      <p className="flex items-center gap-2"><Clock aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
        <span><span className="font-medium">{space}</span>{" · "}
          <span className="tabular-nums">{t`${left} h left of ${pool} h`}</span>
          {bank.period_ends_at ? <span className="text-muted">{t` · resets ${formatDate(bank.period_ends_at)}`}</span> : null}</span></p>
      <details className="mt-1"><summary className="cursor-pointer text-sm text-muted">{t`Hours ledger for ${space}`}</summary>
        <LedgerPeek organizationId={organizationId} makerspaceId={bank.makerspace_id} /></details>
    </li>;
  })}</ul>;
}
