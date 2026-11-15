import type { PaginatedResponse } from "../types/inventory";

/** Existing public filters and pickers need every option from the paginated API. */
export async function collectPublicPages<T>(fetchPage: (page: number) => Promise<PaginatedResponse<T>>): Promise<T[]> {
  const rows: T[] = [];
  for (let number = 1; ; number += 1) {
    const page = await fetchPage(number);
    rows.push(...page.results);
    if (!page.next) return rows;
  }
}
