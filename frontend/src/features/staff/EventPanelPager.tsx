import { Pagination } from "../../components/ui";

/** DRF `PageNumberPagination` page size, the standing convention for every list endpoint. */
const PAGE_SIZE = 24;

/**
 * The event drawers' pager: a thin adapter from a DRF page (`count`/`next`/`previous`) to the shared
 * `Pagination`, so every drawer pages the same way. Hidden when everything fits on one page.
 */
export function EventPanelPager({ page, setPage, count, next, disabled }: {
  page: number; setPage: (page: number) => void; count?: number; next?: string | null; previous?: string | null; disabled?: boolean;
}) {
  // A response without `count` still tells us whether another page exists.
  const totalPages = count != null ? Math.ceil(count / PAGE_SIZE) : page + (next ? 1 : 0);
  return <Pagination page={page} totalPages={totalPages} onChange={setPage} disabled={disabled}
    {...(count != null ? { count, pageSize: PAGE_SIZE } : {})} />;
}
