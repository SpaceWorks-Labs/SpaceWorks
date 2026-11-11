import { plural, t } from "@lingui/core/macro";
import { PublicLayout } from "../../components/layouts";
import type { PublicActionCardProps } from "../../components/layouts/PublicActionCard";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { publicPageChrome } from "./PublicPageChrome";
import { PageMetadata } from "../../components/PageMetadata";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { onSessionCleared } from "../../lib/api/sessionContext";
import { invalidatePublicInventory } from "../staff/queryInvalidation";
import type { SelfResult } from "./contextualIntake";
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
import { usePendingIntakeOwner } from "./usePendingIntakeOwner";
import { useIntakeScope } from "./useIntakeScope";
import { useRequestDraft } from "./useRequestDraft";
import { useInventoryCart } from "./publicInventory/useInventoryCart";
import { usePublicCategories, usePublicInventory, useTenantBootstrap } from "./usePublicInventory";

const PAGE_SIZE = 24;

/** A host that supplies its own chrome (the public desk) places the inventory body and
 * request panel itself; `aside` is the same request card the standalone catalogue docks beside its body. */
export type EmbeddedCatalogue = (parts: { body: ReactNode; request: ReactNode; aside: PublicActionCardProps }) => ReactNode;

export function PublicInventoryPage({ embedded, resolvedSlug, inheritBranding = false }: {
  embedded?: EmbeddedCatalogue; resolvedSlug?: string; inheritBranding?: boolean;
}) {
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
  const [planSuccessScope, setPlanSuccessScope] = useState<string>();
  const requestDraft = useRequestDraft();
  const session = useIntakeScope();
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
    ? { status: "error" as const, error: t`Couldn't load inventory. Try again.`, onRetry: () => { void inventoryQuery.refetch(); } } : { status: "ready" as const };
  const body = <div className="grid min-w-0 gap-6">
    <CatalogSidebar categories={categories} view={view} onSelect={selectView} />
    <Card><form className="flex flex-wrap items-end gap-3" onSubmit={submitSearch}>
      <Field className="min-w-0 flex-1" label={t`Search inventory`}><input className="desk-input w-full bg-success text-on-success placeholder:text-on-success" placeholder={t`Search tools, machines, kits, or materials`} value={searchInput} onChange={event => setSearchInput(event.target.value)} /></Field>
      <button className="desk-button-brand" type="submit">{t`Search`}</button>
      {query ? <button className="desk-button" type="button" onClick={() => { setSearchInput(""); setQuery(""); setPage(1); }}>{t`Clear`}</button> : null}
    </form></Card>
    <QueryContent state={state} isEmpty={!products.length} empty={{ message: query ? t`No matching items. Try another search.` : t`No public items yet. Check back soon.`, action: query ? { label: t`Clear search`, onClick: () => { setSearchInput(""); setQuery(""); setPage(1); } } : undefined }}>
    {/* Columns come from the space the catalogue actually has (it shares the row with the request panel
      at xl, and with the request column on the desk kiosk), not from the viewport width. */}
    <div className="grid grid-cols-[repeat(auto-fill,minmax(min(100%,15rem),1fr))] gap-4">{products.map(product => <ProductCard key={product.id} product={product}
      quantity={cart[product.id]?.quantity ?? 0} onDecrement={() => decrementItem(product)} onIncrement={() => incrementItem(product)}
      onOpenDetails={() => setSelectedProduct(product)} detailUrl={tenantPath(`items/${product.id}`)} eventsOn={modules.has("events")} />)}</div>
    <Pagination page={page} totalPages={pageCount} count={inventoryQuery.data?.count} pageSize={PAGE_SIZE} onChange={setPage} disabled={inventoryQuery.isFetching} />
    </QueryContent>
  </div>;
  const requestScope = JSON.stringify([session.context, session.owner, makerspaceSlug, bootstrap?.makerspace.id ?? null]);
  useEffect(() => { setPlanSuccessScope(undefined); }, [requestScope]);
  useEffect(() => onSessionCleared(context => {
    if (context === session.context && getSessionOwner(context) !== session.owner) setPlanSuccessScope(undefined);
  }), [session.context, session.owner]);
  const pendingOwner = usePendingIntakeOwner(requestScope);
  const queryClient = useQueryClient();
  const liveRequest = useRef({ scope: requestScope, owner: session.owner, slug: makerspaceSlug, live: false });
  liveRequest.current.scope = requestScope; liveRequest.current.owner = session.owner; liveRequest.current.slug = makerspaceSlug;
  useEffect(() => { liveRequest.current.live = true; return () => { liveRequest.current.live = false; }; }, []);
  const contextSuccess = (result: SelfResult, completedScope: string) => {
    const current = liveRequest.current;
    const verified = queryClient.getQueryData<{ id: number }>(["member", "cards-account"]);
    if (!current.live || completedScope !== current.scope || !current.owner ||
        getSessionOwner("person") !== current.owner || String(verified?.id) !== current.owner) return;
    invalidatePublicInventory(queryClient, current.slug);
    clearCart(); requestDraft.setRequestedFor(""); requestDraft.setWebsite("");
    requestDraft.setPickup({ from: "", until: "" }); requestDraft.setSubmitted(result.kind === "request");
    setPlanSuccessScope(result.kind === "consumable_plan" ? completedScope : undefined);
  };
  const contextualLocked = useSyncExternalStore(listener => pendingOwner.subscribe(listener), () => pendingOwner.has(requestScope), () => false);
  const request = <PublicRequestPanel items={selectedItems} makerspaceSlug={makerspaceSlug} onClear={clearCart} disabled={!requestEnabled} requestAccess={bootstrap?.makerspace.request_access}
    activeTab={requestTab} onActiveTabChange={setRequestTab} draft={requestDraft} features={bootstrap?.features} makerspaceId={bootstrap?.makerspace.id} modules={[...modules]} pendingOwner={pendingOwner} contextualLocked={contextualLocked} onContextSuccess={contextSuccess} planConfirmed={planSuccessScope === requestScope} onNewRequest={() => setPlanSuccessScope(undefined)} />;
  const totalItems = selectedItems.reduce((total, item) => total + item.quantity, 0);
  const aside: PublicActionCardProps = { title: t`Your request`, form: request, state: "open", mobileBar: { summary: plural(totalItems, { one: "Request - # item", other: "Request - # items" }), label: t`Review request`, onOpen: () => setRequestTab("borrow"),
    secondary: requestEnabled && bootstrap?.features.includes("inventory.self_checkout") ? { label: t`Scan a tool`, onOpen: () => setRequestTab("scan") } : undefined } };
  // A composed public page owns its palette; the standalone catalogue and desk still apply tenant branding.
  return <div style={inheritBranding ? undefined : brandStyle}>
    {!embedded ? <PageMetadata title={t`Inventory · ${displayName}`} description={t`Browse public tools and equipment at ${displayName}.`} path={tenantPath("inventory")} image={bootstrap?.makerspace.cover_image_url || bootstrap?.makerspace.logo_url} siteName={displayName} /> : null}
    {embedded ? embedded({ body, request, aside })
      : <PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)} width="wide" state={{ status: "ready" }}
        header={{ title: t`Inventory`, subtitle: t`Borrow tools and kits from ${displayName}.`, primary: { label: t`Member area`, href: tenantPath("member") } }}
        isEmpty={false} aside={aside}>
        {body}
      </PublicLayout>}

    <ProductQuickViewModal product={selectedProduct} open={Boolean(selectedProduct)} onClose={() => setSelectedProduct(null)}
      makerspaceId={bootstrap?.makerspace.id} features={bootstrap?.features} eventsOn={modules.has("events")} />
  </div>;
}
