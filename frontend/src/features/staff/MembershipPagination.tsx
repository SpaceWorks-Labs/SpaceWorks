import { PagePager } from "../../components/ui";

/** Roster pager used by the membership, community and presence desks: a DRF page over the shared `Pagination`. */
export function MembershipPagination({ page, next, fetching, onPage }: {
  label?: string; page: number; next?: string | null; previous?: string | null;
  fetching: boolean; onPage: (page: number) => void;
}) {
  return <div className="mt-3"><PagePager page={page} setPage={onPage} next={next} disabled={fetching} /></div>;
}
