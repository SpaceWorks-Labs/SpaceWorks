import { t } from "@lingui/core/macro";
import { RouteLink } from "../../../components/ui/RouteLink";
import { useCrossLink } from "../crossLinks/staffHref";
import { ListLayout } from "../../../components/layouts";
import { inventoryQueryState } from "./inventoryPresentation";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ConfirmDialog, DataTable, Field, Modal, OverflowMenu } from "../../../components/ui";
import type { DataTableColumn } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { categoryResults, type Category, type CategoryListResponse, type Makerspace, useStaffGet } from "./shared";
import { invalidatePublicInventory } from "../queryInvalidation";
import { BoxArt } from "../../../components/BoxSpinner";

type CategoryForm = {
  name: string;
  slug: string;
  display_order: string;
  icon: string;
};

const emptyCategoryForm: CategoryForm = {
  name: "",
  slug: "",
  display_order: "",
  icon: "",
};

function categoryPayload(form: CategoryForm, includeSlug: boolean) {
  return {
    name: form.name.trim(),
    ...(includeSlug && form.slug.trim() ? { slug: form.slug.trim() } : {}),
    ...(form.display_order ? { display_order: Number(form.display_order) } : {}),
    icon: form.icon.trim(),
  };
}

export function Categories({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const link = useCrossLink();
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<CategoryForm>(emptyCategoryForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<CategoryForm>(emptyCategoryForm);
  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null);
  const categories = useStaffGet<CategoryListResponse>(
    ["categories", makerspace.id],
    `/admin/makerspace/${makerspace.id}/categories`,
  );
  const invalidateCategories = () => {
    queryClient.invalidateQueries({ queryKey: ["categories", makerspace.id] });
    queryClient.invalidateQueries({ queryKey: ["inventory", makerspace.id] });
    invalidatePublicInventory(queryClient, makerspace.slug);
  };
  const create = useMutation({
    mutationFn: () =>
      staffRequest(`/admin/makerspace/${makerspace.id}/categories`, {
        method: "POST",
        body: JSON.stringify(categoryPayload(form, true)),
      }),
    onSuccess: () => {
      setForm(emptyCategoryForm);
      setAddOpen(false);
      invalidateCategories();
    },
  });
  const update = useMutation({
    mutationFn: (category: Category) =>
      staffRequest(`/admin/categories/${category.id}`, {
        method: "PATCH",
        body: JSON.stringify(categoryPayload(editForm, false)),
      }),
    onSuccess: () => {
      setEditingId(null);
      invalidateCategories();
    },
  });
  const remove = useMutation({
    mutationFn: (category: Category) =>
      staffRequest(`/admin/categories/${category.id}`, {
        method: "DELETE",
      }).catch((error: unknown) => {
        if (error instanceof SyntaxError) return undefined;
        throw error;
      }),
    onSuccess: () => {
      setDeleteTarget(null);
      invalidateCategories();
    },
  });
  const rows = categoryResults(categories.data);
  const startEdit = (category: Category) => {
    setEditingId(category.id);
    setEditForm({
      name: category.name,
      slug: category.slug,
      display_order: String(category.display_order),
      icon: category.icon ?? "",
    });
  };
  const columns: DataTableColumn<Category>[] = [
    {
      key: "name",
      header: t`Name`,
      sortable: true,
      render: (category) =>
        editingId === category.id ? (
          <input
            className="desk-input w-full"
            aria-label={t`Name for ${category.name}`}
            value={editForm.name}
            onChange={(event) => setEditForm((current) => ({ ...current, name: event.target.value }))}
          />
        ) : (
          <span className="font-semibold">{category.name}</span>
        ),
    },
    { key: "slug", header: t`Slug`, sortable: true },
    {
      key: "display_order",
      header: t`Order`,
      sortable: true,
      render: (category) =>
        editingId === category.id ? (
          <input
            className="desk-input w-24"
            aria-label={t`Order for ${category.name}`}
            type="number"
            value={editForm.display_order}
            onChange={(event) => setEditForm((current) => ({ ...current, display_order: event.target.value }))}
          />
        ) : (
          category.display_order
        ),
    },
    {
      key: "icon",
      header: t`Icon`,
      render: (category) =>
        editingId === category.id ? (
          <input
            className="desk-input w-28"
            aria-label={t`Icon for ${category.name}`}
            value={editForm.icon}
            onChange={(event) => setEditForm((current) => ({ ...current, icon: event.target.value }))}
          />
        ) : (
          category.icon || "-"
        ),
    },
    // IN9: the count opens the stock list narrowed to this category.
    { key: "product_count", header: t`Products`, sortable: true, render: (category) => {
      const href = link("inventory", { category: category.id });
      return href ? <RouteLink className="font-semibold underline" href={href} aria-label={t`${category.product_count} items in ${category.name}`}>{category.product_count}</RouteLink> : category.product_count;
    } },
    {
      key: "actions",
      header: "",
      render: (category) =>
        editingId === category.id ? (
          <div className="desk-actions flex flex-wrap gap-2">
            <button
              className="desk-button-primary"
              type="button"
              disabled={!editForm.name.trim() || update.isPending}
              onClick={() => update.mutate(category)}
            >
              {update.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save`}
            </button>
            <button className="desk-button-ghost" type="button" onClick={() => setEditingId(null)}>
              {t`Cancel`}</button>
          </div>
        ) : (
          <div className="flex items-center gap-2"><button className="desk-button-ghost" onClick={() => startEdit(category)}>{t`Edit`}</button>
          <OverflowMenu label={t`Actions for ${category.name}`} actions={[{ label: t`Delete`, confirms: true, tone: "danger", disabled: remove.isPending, onClick: () => setDeleteTarget(category) }]} /></div>
        ),
    },
  ];
  const add = { label: t`Add category`, onClick: () => setAddOpen(true) };
  return <ListLayout header={{ title: t`Categories`, subtitle: t`Group the parts in your catalogue.`, primary: add }}
    state={inventoryQueryState(categories, "categories")} isEmpty={!rows.length} empty={{ message: t`No categories yet. Add one to group your catalogue.`, action: add }}
    body={{ kind: "table", table: <DataTable<Category> columns={columns} data={rows} getRowId={row => row.id} /> }}
    detail={<><Modal open={addOpen} onClose={() => setAddOpen(false)} title={t`Add category`}>
        <div className="grid gap-4">
          <Field label={t`Name`}><input className="desk-input" value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} /></Field>
          <Field label={t`Slug`}><input className="desk-input" placeholder={t`auto from name`} value={form.slug} onChange={(event) => setForm((current) => ({ ...current, slug: event.target.value }))} /></Field>
          <Field label={t`Order`}><input className="desk-input" type="number" value={form.display_order} onChange={(event) => setForm((current) => ({ ...current, display_order: event.target.value }))} /></Field>
          <Field label={t`Icon`}><input className="desk-input" value={form.icon} onChange={(event) => setForm((current) => ({ ...current, icon: event.target.value }))} /></Field>
          <button className="desk-button-primary" type="button" disabled={!form.name.trim() || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? <><BoxArt size={16} mono />{t`Adding…`}</> : t`Add category`}
          </button>
        </div>
      {create.error ? <p role="alert" className="text-sm text-danger">{create.error.message}</p> : null}</Modal>
      {update.error || remove.error ? <p role="alert" className="text-sm text-danger">{(update.error || remove.error)?.message}</p> : null}
      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={t`Delete category`}
        message={
          deleteTarget
            ? t`Delete ${deleteTarget.name}? This will detach ${deleteTarget.product_count} products.`
            : ""
        }
        confirmLabel={t`Delete`}
        tone="danger"
        pending={remove.isPending}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={() => {
          if (deleteTarget) remove.mutate(deleteTarget);
        }}
      />
    </>} />;
}
