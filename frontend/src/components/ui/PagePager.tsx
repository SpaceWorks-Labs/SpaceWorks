import { Pagination } from "./Pagination";

/** DRF `PageNumberPagination` page size, the standing convention for every list endpoint. */
const PAGE_SIZE = 24;

/**
 * Adapter from a DRF page (`count`/`next`) to the shared `Pagination`, so every hand-paged list
 * (member, public and staff) pages the same way. Hidden when everything fits on one page. Without a
 * `count` it still knows whether another page exists from `next`.
 */
export function PagePager({ page, setPage, count, next, disabled }: {
  page: number; setPage: (page: number) => void; count?: number; next?: string | null; disabled?: boolean;
}) {
  const totalPages = count != null ? Math.ceil(count / PAGE_SIZE) : page + (next ? 1 : 0);
  return <Pagination page={page} totalPages={totalPages} onChange={setPage} disabled={disabled}
    {...(count != null ? { count, pageSize: PAGE_SIZE } : {})} />;
}
