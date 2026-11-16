import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";

import { LogoLoader } from "../../../components/LogoLoader";
import { RelativeTime, StatusPill } from "../../../components/ui";
import { shelfApi, shelfKeys } from "./shelfApi";

/** The past shelf checks, newest first: when, who, and how many shelves were fine or flagged. */
export function ShelfCheckHistory({ makerspaceId }: { makerspaceId: number }) {
  const checks = useQuery({ queryKey: shelfKeys.checks(makerspaceId), queryFn: () => shelfApi.checks(makerspaceId), retry: false });
  const rows = checks.data?.results ?? [];
  return <section aria-label={t`Past shelf checks`} className="grid gap-2">
    <h3 className="title-section">{t`Past shelf checks`}</h3>
    {checks.isLoading ? <LogoLoader label={t`Loading…`} size={32} className="min-h-12 py-2" /> : null}
    {!checks.isLoading && !rows.length ? <p className="text-sm text-muted">{t`No shelf checks saved yet.`}</p> : null}
    <ul className="grid gap-2">{rows.map(row => <li key={row.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-line p-3">
      <div className="min-w-0 text-sm"><RelativeTime date={row.created_at} />{row.checked_by_name ? <span className="text-muted">{t` · ${row.checked_by_name}`}</span> : null}
        {row.scope_label ? <span className="block text-xs text-muted [overflow-wrap:anywhere]">{row.scope_label}</span> : null}</div>
      <div className="flex flex-wrap gap-2"><StatusPill tone="success" label={t`${row.ok_count} OK`} />
        {row.attention_count ? <StatusPill tone="warn" label={t`${row.attention_count} need attention`} /> : null}</div></li>)}</ul>
  </section>;
}
