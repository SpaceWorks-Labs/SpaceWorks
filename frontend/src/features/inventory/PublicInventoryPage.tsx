import { plural } from "../../lib/plural";
import { PublicLayout } from "../../components/layouts";
import type { PublicActionCardProps } from "../../components/layouts/PublicActionCard";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { publicPageChrome } from "./PublicPageChrome";
import { PageMetadata } from "../../components/PageMetadata";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useParams } from "react-router-dom";

import { Card, Field, Pagination } from "../../components/ui";
import { useTenant, useTenantPath } from "../../lib/tenant";
import type { Product } from "../../types/inventory";
import { ProductCard } from "./ProductCard";
import { ProductQuickViewModal } from "./ProductQuickViewModal";
import {
  CatalogSidebar,
  formatSlug,
  type View,
} from "./PublicInventoryParts";
import { PublicRequestPanel, type ActiveTab } from "./PublicRequestPanel";
import { useRequestDraft } from "./useRequestDraft";
import { useInventoryCart } from "./publicInventory/useInventoryCart";
import { usePublicCategories, usePublicInventory, useTenantBootstrap } from "./usePublicInventory";

const PAGE_SIZE = 24;

/** A host that supplies its own chrome (the public desk, the makerspace page) places the catalogue body and
 * request panel itself; `aside` is the same request card the standalone catalogue docks beside its body. */
export type EmbeddedCatalogue = (parts: { body: ReactNode; request: ReactNode; aside: PublicActionCardProps }) => ReactNode;

export function PublicInventoryPage({ embedded, resolvedSlug }: { embedded?: EmbeddedCatalogue; resolvedSlug?: string }) {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = resolvedSlug ?? (tenant.mode === "single" ? tenant.slug : slug ?? "");
  const tenantPath = useTenantPath(makerspaceSlug);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>({ kind: "all" });
  const { cart, selectedItems, incrementItem, decrementItem, clearCart } = useInventoryCart();
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [requestTab, setRequestTab] = useState<ActiveTab>("borrow");
  const requestDraft = useRequestDraft();
  const categoryParam = view.kind === "category" ? view.slug : "";
  const sortParam = view.kind === "sort" ? view.sort : "name";
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const categoriesQuery = usePublicCategories(makerspaceSlug);
  const inventoryQuery = usePublicInventory(
    makerspaceSlug,
    page,
    query,
    categoryParam,
    sortParam,
  );
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const displayName =
    bootstrap?.branding.display_name ||
    bootstrap?.makerspace.name ||
    formatSlug(makerspaceSlug) ||
    "Makerspace";
  const modules = tenant.mode === "single" ? tenant.modules : new Set(bootstrap?.modules ?? []);
  const requestEnabled = modules.has("request_workflow");
  const categories = categoriesQuery.data ?? [];
  const products = inventoryQuery.data?.results ?? [];
  const pageCount = Math.max(
    1,
    Math.ceil((inventoryQuery.data?.count ?? 0) / PAGE_SIZE),
  );

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
  }

  function selectView(next: View) {
    setView(next);
    setPage(1);
  }

  // A catalogue refresh must not hide search or an already-composed request.
  const state = inventoryQuery.isLoading ? { status: "loading" as const } : inventoryQuery.isError
    ? { status: "error" as const, error: "Couldn't load inventory. Try again.", onRetry: () => { void inventoryQuery.refetch(); } } : { status: "ready" as const };
  const body = <div className="grid min-w-0 gap-6">
    <CatalogSidebar categories={categories} view={view} onSelect={selectView} />
    <Card><form className="flex flex-wrap items-end gap-3" onSubmit={submitSearch}>
      <Field className="min-w-0 flex-1" label="Search inventory"><input className="desk-input w-full bg-success text-on-success placeholder:text-on-success" placeholder="Search tools, machines, kits, or materials" value={searchInput} onChange={event => setSearchInput(event.target.value)} /></Field>
      <button className="desk-button-brand" type="submit">Search</button>
      {query ? <button className="desk-button" type="button" onClick={() => { setSearchInput(""); setQuery(""); setPage(1); }}>Clear</button> : null}
    </form></Card>
    <QueryContent state={state} isEmpty={!products.length} empty={{ message: query ? "No matching items. Try another search." : "No public items yet. Check back soon.", action: query ? { label: "Clear search", onClick: () => { setSearchInput(""); setQuery(""); setPage(1); } } : undefined }}>
    {/* Columns come from the space the catalogue actually has (it shares the row with the request panel
      at xl, and with the request column on the desk kiosk), not from the viewport width. */}
    <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,15rem),1fr))] gap-4">{products.map(product => <ProductCard key={product.id} product={product}
      quantity={cart[product.id]?.quantity ?? 0} onDecrement={() => decrementItem(product)} onIncrement={() => incrementItem(product)}
      onOpenDetails={() => setSelectedProduct(product)} detailUrl={tenantPath(`items/${product.id}`)} />)}</div>
    <Pagination page={page} totalPages={pageCount} count={inventoryQuery.data?.count} pageSize={PAGE_SIZE} onChange={setPage} disabled={inventoryQuery.isFetching} />
    </QueryContent>
  </div>;
  const request = <PublicRequestPanel items={selectedItems} makerspaceSlug={makerspaceSlug} onClear={clearCart} disabled={!requestEnabled} requestAccess={bootstrap?.makerspace.request_access}
    activeTab={requestTab} onActiveTabChange={setRequestTab} draft={requestDraft} />;
  const totalItems = selectedItems.reduce((total, item) => total + item.quantity, 0);
  const aside: PublicActionCardProps = { title: "Your request", form: request, state: "open", mobileBar: { summary: `Request · ${plural(totalItems, "item")}`, label: "Review request", onOpen: () => setRequestTab("borrow"),
    secondary: requestEnabled ? { label: "Scan a tool", onOpen: () => setRequestTab("scan") } : undefined } };
  return <div style={brandStyle}>
    {!embedded ? <PageMetadata title={displayName} description={bootstrap?.branding.welcome_body || `Browse public tools and equipment at ${displayName}.`} path={tenantPath()} image={bootstrap?.makerspace.cover_image_url || bootstrap?.makerspace.logo_url} siteName={displayName} /> : null}
    {embedded ? embedded({ body, request, aside })
      : <PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)} width="wide" state={{ status: "ready" }}
        header={{ title: `Borrow tools from ${displayName}`, subtitle: `${plural(inventoryQuery.data?.count ?? 0, "tool")} and kits`, primary: { label: "Member area", href: tenantPath("member") } }}
        isEmpty={false} aside={aside}>
        {body}
      </PublicLayout>}

    <ProductQuickViewModal product={selectedProduct} open={Boolean(selectedProduct)} onClose={() => setSelectedProduct(null)} />
  </div>;
}
