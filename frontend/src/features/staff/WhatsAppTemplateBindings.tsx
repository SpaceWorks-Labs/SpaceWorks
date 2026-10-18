import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { SettingsRow, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { MessagingError } from "../messaging/MessagingFeedback";
import { templateBindingsKey, templateBindingsPath, type MessagingCatalogEntry,
  type WhatsAppBinding, type WhatsAppBindingPage, type WhatsAppBindingWrite } from "../messaging/messagingApi";
import { WhatsAppBindingForm } from "./WhatsAppBindingForm";

export function WhatsAppTemplateBindings({ makerspaceId }: { makerspaceId: number }) {
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<WhatsAppBinding | "new" | null>(null);
  const path = templateBindingsPath(makerspaceId);
  const rows = useQuery({ queryKey: [...templateBindingsKey(makerspaceId), page],
    queryFn: () => staffRequest<WhatsAppBindingPage>(`${path}?page=${page}`) });
  const catalog = useQuery({ queryKey: ["whatsapp-template-catalog", makerspaceId],
    queryFn: () => staffRequest<MessagingCatalogEntry[]>(`${path}/catalog`) });
  const save = useMutation({ mutationFn: (body: WhatsAppBindingWrite) => staffRequest<WhatsAppBinding>(
    editing && editing !== "new" ? `${path}/${editing.id}` : path,
    { method: editing === "new" ? "POST" : "PATCH", body: JSON.stringify(body) }),
    onSuccess: () => { setEditing(null); return client.invalidateQueries({ queryKey: templateBindingsKey(makerspaceId) }); },
  });
  const remove = useMutation({ mutationFn: (id: number) => staffRequest<void>(`${path}/${id}`, { method: "DELETE" }),
    onSuccess: () => { setEditing(null); if (page > 1 && rows.data?.results.length === 1) setPage(page - 1);
      return client.invalidateQueries({ queryKey: templateBindingsKey(makerspaceId) }); },
  });
  const busy = save.isPending || remove.isPending;
  return <SettingsRow label="WhatsApp template bindings" helper="Bind templates approved in Meta to reviewed events and audiences. Only positional text BODY parameters are supported; media headers, buttons and named parameters are unsupported. Platform bindings are managed by the operator; these bindings apply to your own WABA.">
    <div className="grid min-w-0 gap-4">
      {rows.isPending || catalog.isPending ? <p role="status">Loading WhatsApp templates…</p> : null}
      <MessagingError error={rows.error || catalog.error} />
      {rows.isError || catalog.isError ? <button className="desk-button w-fit" type="button" onClick={() => { void rows.refetch(); void catalog.refetch(); }}>Retry templates</button> : null}
      {rows.data?.results.length === 0 ? <p className="text-sm text-muted">No template bindings yet.</p> : null}
      {rows.data?.results.map(row => <section key={row.id} className="grid gap-2 rounded-md border border-line p-3">
        <h3 className="text-sm font-semibold break-words">{row.feature} / {row.event} / {row.audience}</h3>
        <p className="text-sm break-words">{row.template_name} ({row.language}) · {row.is_active ? "Active" : "Inactive"}</p>
        <p className="text-sm text-muted break-words">BODY parameters: {row.parameters.join(", ") || "None"}</p>
        {row.needs_review ? <><StatusPill label="Needs review" tone="warn" /><p className="text-sm text-warn-ink">The business account changed or this binding was imported. Review and save it against your current WABA before delivery can resume.</p></> : null}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button" disabled={busy || !catalog.isSuccess} onClick={() => { save.reset(); setEditing(row); }}>Edit {row.template_name}</button>
          <button type="button" className="desk-button-danger-outline" disabled={busy} onClick={() => remove.mutate(row.id)}>Delete {row.template_name}</button>
        </div>
      </section>)}
      {rows.data && (rows.data.previous || rows.data.next) ? <nav className="flex items-center gap-3" aria-label="Template pages">
        <button type="button" className="desk-button" disabled={!rows.data.previous || busy} onClick={() => setPage(page - 1)}>Previous templates</button>
        <span>Page {page}</span><button type="button" className="desk-button" disabled={!rows.data.next || busy} onClick={() => setPage(page + 1)}>Next templates</button>
      </nav> : null}
      {!editing ? <button type="button" className="desk-button w-fit" disabled={busy || !catalog.data?.length} onClick={() => { save.reset(); setEditing("new"); }}>Add template binding</button> : null}
      {catalog.isSuccess && !catalog.data.length ? <p className="text-sm text-muted">No reviewed events available for binding.</p> : null}
      {editing && catalog.data ? <WhatsAppBindingForm key={editing === "new" ? "new" : editing.id} catalog={catalog.data}
        initial={editing === "new" ? undefined : editing} pending={busy} onSave={body => save.mutate(body)} onCancel={() => { setEditing(null); save.reset(); }} /> : null}
      <MessagingError error={save.error || remove.error} />
      {save.isSuccess || remove.isSuccess ? <p role="status" className="text-sm text-success-ink">Template bindings updated.</p> : null}
    </div>
  </SettingsRow>;
}
