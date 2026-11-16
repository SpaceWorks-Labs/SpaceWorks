import { t } from "@lingui/core/macro";

import type { Category } from "./shared";

/** IN9: narrow the stock list to one category (`?category=` is also the Categories page's click-through). */
export function InventoryCategoryFilter({ categories, value, onChange }: {
  categories: Category[]; value: string; onChange: (value: string) => void;
}) {
  if (!categories.length) return null;
  return <label className="grid min-w-0 gap-1 text-sm">{t`Category`}
    <select className="desk-input max-w-full" value={value} onChange={event => onChange(event.target.value)}>
      <option value="">{t`All categories`}</option>
      {categories.map(category => <option key={category.id} value={String(category.id)}>{category.name}</option>)}
    </select>
  </label>;
}
