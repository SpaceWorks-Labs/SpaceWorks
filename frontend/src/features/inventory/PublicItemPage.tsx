import { t } from "@lingui/core/macro";
import { CenteredCardLayout, PublicLayout, PublicDetailLayout } from "../../components/layouts";
import { publicPageChrome } from "./PublicPageChrome";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { PageMetadata } from "../../components/PageMetadata";
import { Card } from "../../components/ui";
import { StructuredApiError, isSurfaceOff, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBranding } from "../../lib/useTenantBranding";
import type { Product } from "../../types/inventory";
import { NotifyWhenBack } from "./NotifyWhenBack";
import { AvailabilityBadge } from "./AvailabilityBadge";
import { useTenantBootstrap } from "./usePublicInventory";
import { ExpectedBack } from "./ExpectedBack";
import { publicFamilies } from "../../lib/publicHome";
import { ItemRequestForm, useItemRequestDraft } from "./ItemRequestForm";
import { WaitlistJoin } from "./WaitlistJoin";

// The numeric identity is stable even if the optional readable suffix changes.
export function publicItemId(value: string) {
  const id = value.split("-")[0];
  return /^[1-9]\d*(?:-[^/]+)?$/.test(value) && Number.isSafeInteger(Number(id)) ? id : null;
}

export function PublicItemPage() {
  const { slug = "", itemId = "" } = useParams();
  const tenant = useTenant();
  const spaceSlug = tenant.mode === "single" ? tenant.slug : slug;
  const tenantPath = useTenantPath(spaceSlug);
  const bootstrapQuery = useTenantBootstrap(spaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const id = publicItemId(itemId);
  const requestDraft = useItemRequestDraft(id);
  const item = useQuery({
    queryKey: ["public-inventory-detail", spaceSlug, id],
    queryFn: () => tenantPublicRequest<Product>(spaceSlug, `/public/${encodeURIComponent(spaceSlug)}/inventory/${id}/`),
    enabled: Boolean(spaceSlug && id),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
  const product = item.error ? undefined : item.data;
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || "Makerspace";
  const disabled = isSurfaceOff(item.error);
  const missing = !id || (!disabled && item.error instanceof StructuredApiError && item.error.status === 404);
  const title = missing ? "Item not found" : disabled ? "Inventory is not enabled" : product?.name ?? "Item details";
  const description = product?.description || `Browse public tools and equipment at ${name}.`;
  const modules = new Set(bootstrap?.modules ?? []);
  const requestEnabled = Boolean(bootstrap && publicFamilies(bootstrap).includes("inventory") && modules.has("request_workflow") && product && !product.event_only);
  const eventsOn = modules.has("events"); // decision 228a: no event route to point at while Events is off
  const state = !bootstrap && bootstrapQuery.error ? { status: "error" as const, error: t`Couldn't load this space. Try again.`, onRetry: () => { void bootstrapQuery.refetch(); } } : !bootstrap || id && item.isLoading ? { status: "loading" as const } : item.error || missing
    ? { status: "error" as const, error: missing ? t`This item isn't in the public catalogue.` : disabled ? t`This makerspace is not publishing inventory.` : t`Couldn't load this item. Try again.`, onRetry: () => { void item.refetch(); } }
    : { status: "ready" as const };
  if (missing || disabled) return <div style={brandStyle}><PageMetadata title={`${title} · ${name}`} description={description} path={tenantPath(`items/${id ?? itemId}`)} image={bootstrap?.makerspace.logo_url} siteName={name} /><CenteredCardLayout state={{ status: "ready" }} title={title}
    body={missing ? t`This item isn't in the public catalogue.` : t`This makerspace is not publishing inventory.`}
    primary={{ label: t`Back to inventory`, href: tenantPath("inventory") }} /></div>;
  return <div style={brandStyle}>
    <PageMetadata title={`${title} · ${name}`} description={description} path={tenantPath(`items/${product?.id ?? id ?? itemId}`)} image={product?.image_url || bootstrap?.makerspace.logo_url} siteName={name} />
    <PublicLayout {...publicPageChrome(spaceSlug, name, tenantPath, bootstrap)} state={state}
      breadcrumb={[{ label: t`Inventory`, href: tenantPath("inventory") }, { label: title }]}>
      <PublicDetailLayout title={title} state={state} cover={product?.image_url ? { src: product.image_url, alt: product.name } : undefined}
        chips={product?.category_name ? [{ label: product.category_name }] : []}
        sections={product ? [{ id: "description", label: t`Description`, content: <p className="whitespace-pre-wrap leading-7">{product.description || t`No description provided.`}</p> },
          ...(product.borrowing_terms ? [{ id: "borrowing", label: t`Borrowing terms`, content: <Card>{product.borrowing_terms}</Card> }] : [])] : []}
        actionCard={{ title: t`Borrow this item`, state: "open", summary: product ? <><AvailabilityBadge availability={product.availability} eventsOn={eventsOn} /><ExpectedBack product={product} className="mt-2" /></> : null,
          form: product?.event_only ? <p className="text-sm text-muted">{eventsOn ? t`This item is lent only at events. Register for an event that offers it, and the organizers can request it for you.` : t`Not available to borrow right now`}</p>
            : product ? <>{bootstrap?.features.includes("inventory.notify_when_back") ? <NotifyWhenBack slug={spaceSlug} productId={product.id} /> : null}
            <WaitlistJoin makerspaceId={bootstrap?.makerspace.id} product={product} features={bootstrap?.features} />
            {requestEnabled && bootstrap ? <ItemRequestForm key={product.id} product={product} bootstrap={bootstrap} state={requestDraft} /> : null}</> : null,
          mobileBar: { initiallyOpen: requestEnabled && requestDraft.returning, summary: product?.name ?? t`Item details`, label: requestEnabled ? t`Request` : t`Item details` } }} />
    </PublicLayout>
  </div>;
}
