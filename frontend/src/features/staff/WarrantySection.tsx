import { t } from "@lingui/core/macro";
import { ConfirmDialog, ErrorBlock, SettingsActions, SettingsRow, Skeleton } from "../../components/ui";
import { useEffect, useId, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { WarrantyStatusBadge } from "./WarrantyStatusBadge";
import {
  deleteWarrantyDocument,
  getWarranty,
  getWarrantyDocumentUrl,
  saveWarranty,
  uploadWarrantyDocument,
  type Warranty,
  type WarrantyHostKind,
  type WarrantyPayload,
} from "./warrantyApi";

type WarrantySectionProps = {
  hostKind: WarrantyHostKind;
  hostId: number;
  disabled?: boolean;
};

type WarrantyForm = {
  purchased_on: string;
  warranty_expires_on: string;
  vendor_name: string;
  vendor_contact: string;
};

const emptyForm: WarrantyForm = {
  purchased_on: "",
  warranty_expires_on: "",
  vendor_name: "",
  vendor_contact: "",
};

const acceptedDocumentTypes = "application/pdf,image/jpeg,image/png,image/webp";

export function WarrantySection({ hostKind, hostId, disabled = false }: WarrantySectionProps) {
  const queryClient = useQueryClient();
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const queryKey = ["warranty", hostKind, hostId] as const;
  const warranty = useQuery({
    queryKey,
    queryFn: () => getWarranty(hostKind, hostId),
  });
  const [form, setForm] = useState<WarrantyForm>(emptyForm);
  const [documentError, setDocumentError] = useState("");
  const [deleteId, setDeleteId] = useState<number | null>(null);

  useEffect(() => {
    setForm(formFromWarranty(warranty.data ?? null));
  }, [warranty.data]);

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey });
    queryClient.invalidateQueries({ queryKey: ["warranties"] });
  };

  const save = useMutation({
    mutationFn: () => saveWarranty(hostKind, hostId, payloadFromForm(form)),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, updated);
      queryClient.invalidateQueries({ queryKey: ["warranties"] });
    },
  });

  const upload = useMutation({
    mutationFn: async (files: File[]) => {
      if (!warranty.data) throw new Error(t`Save warranty details first to attach documents.`);
      for (const file of files) {
        await uploadWarrantyDocument(warranty.data.id, file);
      }
    },
    onSuccess: () => {
      setDocumentError("");
      if (inputRef.current) inputRef.current.value = "";
      invalidate();
    },
    onError: (err) => setDocumentError(err instanceof Error ? err.message : t`Upload failed.`),
  });

  const remove = useMutation({
    mutationFn: deleteWarrantyDocument,
    onSuccess: () => { setDeleteId(null); invalidate(); },
  });

  const current = warranty.data;
  const documents = current?.documents ?? [];

  async function openDocument(documentId: number) {
    setDocumentError("");
    try {
      const { url } = await getWarrantyDocumentUrl(documentId);
      window.open(url, "_blank", "noopener");
    } catch (err) {
      setDocumentError(err instanceof Error ? err.message : t`Could not open document.`);
    }
  }

  return (
    <section className="min-w-0 rounded-md border border-line bg-bg p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="title-section">{t`Warranty`}</h4>
        <WarrantyStatusBadge status={current?.status ?? "unknown"} />
      </div>

      {warranty.isLoading ? <Skeleton className="mt-4 h-40" /> : null}
      {warranty.error ? <ErrorBlock resource="warranty details" error={warranty.error} onRetry={() => { void warranty.refetch(); }} /> : null}

      <div className="mt-3 divide-y divide-line">
        <WarrantyInput
          label={t`Purchased`}
          type="date"
          value={form.purchased_on}
          disabled={disabled || save.isPending}
          onChange={(value) => setForm((currentForm) => ({ ...currentForm, purchased_on: value }))}
        />
        <WarrantyInput
          label={t`Expires`}
          type="date"
          value={form.warranty_expires_on}
          disabled={disabled || save.isPending}
          onChange={(value) => setForm((currentForm) => ({ ...currentForm, warranty_expires_on: value }))}
        />
        <WarrantyInput
          label={t`Vendor`}
          value={form.vendor_name}
          disabled={disabled || save.isPending}
          onChange={(value) => setForm((currentForm) => ({ ...currentForm, vendor_name: value }))}
        />
        <WarrantyInput
          label={t`Contact`}
          value={form.vendor_contact}
          disabled={disabled || save.isPending}
          onChange={(value) => setForm((currentForm) => ({ ...currentForm, vendor_contact: value }))}
        />
      </div>

      {!disabled && (!current || JSON.stringify(form) !== JSON.stringify(formFromWarranty(current))) ? <SettingsActions pending={save.isPending}
        onDiscard={() => setForm(formFromWarranty(current ?? null))} onSave={() => save.mutate()} /> : null}
      {save.error ? <ErrorBlock error={save.error} /> : null}

      <div className="mt-3 border-t border-line pt-3">
        <h5 className="title-section">{t`Documents`}</h5>
        {documents.length ? (
          <div className="mt-2 grid gap-2">
            {documents.map((document) => (
              <div key={document.id} className="flex min-w-0 flex-wrap items-center gap-2 rounded-md border border-line bg-surface px-2 py-1.5 text-xs">
                <span className="min-w-0 flex-1 break-words text-ink">{document.original_filename}</span>
                <span className="tabular-nums text-muted">{formatBytes(document.size_bytes)}</span>
                <button type="button" className="desk-button text-xs" onClick={() => openDocument(document.id)}>
                  {t`View`}</button>
                {!disabled ? (
                  <button
                    type="button"
                    className="desk-button-danger text-xs"
                    disabled={remove.isPending}
                    onClick={() => setDeleteId(document.id)}
                  >
                    {t`Remove…`}</button>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted">{t`No documents attached.`}</p>
        )}

        {!disabled ? (
          current ? (
            <div className="mt-2">
              <label htmlFor={inputId} className="sr-only">{t`Add warranty documents`}</label>
              <input
                id={inputId}
                ref={inputRef}
                type="file"
                multiple
                accept={acceptedDocumentTypes}
                disabled={upload.isPending}
                onChange={(event) => {
                  const files = Array.from(event.target.files ?? []);
                  if (files.length) upload.mutate(files);
                }}
                className="block min-h-11 w-full max-w-full min-w-0 text-xs text-muted file:mr-3 file:rounded-lg file:border file:border-line file:bg-accent file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-on-accent"
              />
              {upload.isPending ? <p className="mt-1 text-xs text-muted">{t`Uploading…`}</p> : null}
            </div>
          ) : (
            <p className="mt-2 text-xs text-muted">{t`Save warranty details first to attach documents.`}</p>
          )
        ) : null}
        {documentError ? <p className="mt-2 text-xs text-danger">{documentError}</p> : null}
        {remove.error instanceof Error ? <p className="mt-2 text-xs text-danger">{remove.error.message}</p> : null}
      </div>
      <ConfirmDialog open={deleteId !== null} title={t`Remove warranty document?`} message={t`The file will no longer be attached to this warranty.`} confirmLabel={t`Remove`} tone="danger" pending={remove.isPending} onCancel={() => setDeleteId(null)} onConfirm={() => { if (deleteId !== null) remove.mutate(deleteId); }} />
    </section>
  );
}

function WarrantyInput({
  label,
  value,
  onChange,
  disabled,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  type?: "text" | "date";
}) {
  return (
    <SettingsRow label={label}>
      <input
        className="desk-input min-w-0"
        type={type}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </SettingsRow>
  );
}

function formFromWarranty(warranty: Warranty | null): WarrantyForm {
  if (!warranty) return emptyForm;
  return {
    purchased_on: warranty.purchased_on ?? "",
    warranty_expires_on: warranty.warranty_expires_on ?? "",
    vendor_name: warranty.vendor_name ?? "",
    vendor_contact: warranty.vendor_contact ?? "",
  };
}

function payloadFromForm(form: WarrantyForm): WarrantyPayload {
  return {
    purchased_on: form.purchased_on || null,
    warranty_expires_on: form.warranty_expires_on || null,
    vendor_name: form.vendor_name.trim(),
    vendor_contact: form.vendor_contact.trim(),
  };
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
