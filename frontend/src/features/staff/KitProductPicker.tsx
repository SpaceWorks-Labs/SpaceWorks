import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { staffRequest } from "../../lib/api";
import type { KitLine } from "../inventory/equipmentKitsApi";
import { PagePager } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";
import { SearchField } from "../../components/ui/SearchField";

type Product = { id: number; name: string; is_consumable: boolean };
type Page = { results: Product[]; next: string | null; previous: string | null };

export function KitProductPicker({ tenant, scope, lines, onChange }: { tenant: number; scope: string; lines: KitLine[]; onChange: (lines: KitLine[]) => void }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["kit-product-picker", scope, search, page], retry: false,
    queryFn: () => staffRequest<Page>(`/admin/makerspace/${tenant}/inventory?page=${page}&archived=false&ordering=name&q=${encodeURIComponent(search)}`) });
  return <div className="grid gap-2">
    <label className="grid gap-1 text-sm">{t`Search inventory`}<SearchField className="desk-input" value={search} onChange={event => { setSearch(event.target.value); setPage(1); }} /></label>
    {query.isPending ? <LogoLoader label={t`Loading items…`} size={48} className="min-h-16 py-3" /> : query.isError ? <p className="text-sm text-danger" role="alert">{t`Inventory is unavailable.`}</p> : <>
      {!query.data.results.length ? <p className="text-sm text-muted">{t`No matching inventory items.`}</p> : null}
      {query.data.results.map(product => <label key={product.id} className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={lines.some(line => line.product_id === product.id)} onChange={event => onChange(event.target.checked ? [...lines, { product_id: product.id, quantity_per_person: 1, kind: product.is_consumable ? "consumable" : "returnable" }] : lines.filter(line => line.product_id !== product.id))} /> {product.name}</label>)}
      <PagePager page={page} setPage={setPage} next={query.data.next} />
    </>}
  </div>;
}
