import { t } from "@lingui/core/macro";
export function MembershipPagination({ label, page, next, previous, fetching, onPage }: {
  label: string; page: number; next?: string | null; previous?: string | null;
  fetching: boolean; onPage: (page: number) => void;
}) {
  return <nav aria-label={`${label} pagination`} className="mt-3 flex flex-wrap items-center gap-3">
    <button className="desk-button" disabled={!previous || fetching} onClick={() => onPage(page - 1)}>{t`Previous ${label}`}</button>
    <span className="text-sm text-muted">{t`Page ${page}`}</span>
    <button className="desk-button" disabled={!next || fetching} onClick={() => onPage(page + 1)}>{t`Next ${label}`}</button>
  </nav>;
}
