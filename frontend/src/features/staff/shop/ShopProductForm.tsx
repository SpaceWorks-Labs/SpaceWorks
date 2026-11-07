import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { FormPageLayout } from "../../../components/layouts";
import { ConfirmDialog } from "../../../components/ui";
import { ImageUploader } from "../ImageUploader";
import { draftFromForm, formFromProduct, formProblem, type ProductForm } from "./productDraft";
import type { ShopAccess } from "./shopAccess";
import { ShopBundleParts } from "./ShopBundleParts";
import { ShopProductFields } from "./ShopProductFields";
import { ShopVariantsEditor, type VariantRow } from "./ShopVariantsEditor";
import {
  archiveVariant, createProduct, fetchProduct, listAllProducts, productImageEndpoint, staffShopError, staffShopKeys, updateProduct,
  type ProductDraft, type ShopProduct,
} from "./staffShopApi";

/** Create or edit one product: its fields, variants and options, kit parts and photo. */
export function ShopProductForm({ makerspaceId, productId, access, onDone }: {
  makerspaceId: number; productId: number | null; access: ShopAccess; onDone: () => void;
}) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: staffShopKeys.product(makerspaceId, productId ?? 0), queryFn: () => fetchProduct(productId!),
    enabled: productId !== null });
  return productId !== null && !query.data
    ? <FormPageLayout header={{ title: t`Product` }} back={{ label: t`Catalogue`, onClick: onDone }} form={null}
      submit={{ label: t`Save`, disabled: true, disabledReason: "Loading the product." }}
      state={query.error ? { status: "error", error: staffShopError(query.error), onRetry: () => { void query.refetch(); } } : { status: "loading" }} />
    : <ProductEditor key={productId ?? "new"} makerspaceId={makerspaceId} product={query.data} access={access} onDone={onDone}
      onSaved={saved => { client.setQueryData(staffShopKeys.product(makerspaceId, saved.id), saved); void client.invalidateQueries({ queryKey: staffShopKeys.all(makerspaceId) }); }} />;
}

function ProductEditor({ makerspaceId, product, access, onDone, onSaved }: {
  makerspaceId: number; product?: ShopProduct; access: ShopAccess; onDone: () => void; onSaved: (product: ShopProduct) => void;
}) {
  const [form, setForm] = useState<ProductForm>(() => formFromProduct(product));
  const [archiving, setArchiving] = useState<VariantRow | null>(null);
  const [tried, setTried] = useState(false);
  const patch = (next: Partial<ProductForm>) => setForm(current => ({ ...current, ...next }));
  const parts = useQuery({ queryKey: staffShopKeys.allProducts(makerspaceId), queryFn: () => listAllProducts(makerspaceId), enabled: access.features.bundles });
  const choices = (parts.data ?? []).filter(row => row.id !== product?.id).flatMap(row => (row.variants ?? [])
    .filter(variant => variant.id && !variant.archived_at).map(variant => ({ id: variant.id as number,
      label: (row.variants?.length ?? 0) > 1 ? `${row.name} · ${variant.name}` : row.name })));
  const save = useMutation({
    mutationFn: () => {
      const draft = draftFromForm(form, access);
      return product ? updateProduct(product.id, draft) : createProduct(makerspaceId, draft as ProductDraft);
    },
    // New variants come back with ids; reload the form so a second save updates them instead of adding copies.
    onSuccess: saved => { onSaved(saved); if (product) setForm(formFromProduct(saved)); else onDone(); },
  });
  const archive = useMutation({ mutationFn: (row: VariantRow) => archiveVariant(row.id!), onSuccess: (_, row) => {
    patch({ variants: form.variants.filter(variant => variant.key !== row.key) }); setArchiving(null);
  } });
  const problem = formProblem(form);
  return <>
    <FormPageLayout state={{ status: "ready" }} back={{ label: t`Catalogue`, onClick: onDone }}
      header={{ eyebrow: t`Shop`, title: product ? product.name : t`New product`, subtitle: product ? undefined : t`You can add a photo after the first save.` }}
      submit={{ label: product ? t`Save changes` : t`Create product`, pending: save.isPending, pendingLabel: "Saving…",
        onClick: () => { setTried(true); if (!problem) save.mutate(); } }}
      cancel={{ label: t`Cancel`, onClick: onDone }}
      form={<div className="grid gap-8">
        {tried && problem ? <p role="alert" className="text-sm text-danger">{problem}</p> : null}
        {save.error ? <p role="alert" className="text-sm text-danger">{staffShopError(save.error)}</p> : null}
        {save.isSuccess && product ? <p role="status" className="text-sm text-muted">{t`Saved.`}</p> : null}
        <ShopProductFields form={form} onChange={patch} access={access} />
        {product ? <ImageUploader endpoint={productImageEndpoint(product.id)} currentUrl={product.image_url || null} label={t`Product photo`}
          onChanged={() => { void fetchProductAgain(); }} /> : null}
        <ShopVariantsEditor rows={form.variants} onChange={variants => patch({ variants })} linkConsumables={access.features.consumableLink}
          showReorder={access.features.reorder} onArchive={row => row.id !== undefined ? setArchiving(row) : patch({ variants: form.variants.filter(v => v.key !== row.key) })} />
        {access.features.bundles ? <ShopBundleParts parts={form.parts} choices={choices} bundleMode={form.bundle_mode}
          onBundleMode={bundle_mode => patch({ bundle_mode })} onChange={next => patch({ parts: next })} /> : null}
        {archive.error ? <p role="alert" className="text-sm text-danger">{staffShopError(archive.error)}</p> : null}
      </div>} />
    <ConfirmDialog open={archiving !== null} title={t`Archive this variant?`} tone="danger" pending={archive.isPending}
      message={t`It leaves the shop and the till. Past orders and stock history keep it.`} confirmLabel={t`Archive variant`}
      onCancel={() => setArchiving(null)} onConfirm={() => { if (archiving) archive.mutate(archiving); }} />
  </>;

  async function fetchProductAgain() {
    if (product) onSaved(await fetchProduct(product.id));
  }
}
