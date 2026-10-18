import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Field } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { deleteDetail, saveDetail } from "./api";
import { fields, textValue, typedValue } from "./fieldPresentation";
import { savedDetailsKey, type SavedField } from "./types";

export function SavedDetailEditor({ actorId, presentation, saved, version }: {
  actorId: number; presentation: typeof fields[number]; saved?: SavedField; version: number;
}) {
  const client = useQueryClient();
  const [text, setText] = useState(textValue(saved?.value));
  const [contact, setContact] = useState(() => saved?.value && typeof saved.value === "object" && "name" in saved.value ? saved.value : { name: "", relationship: "", phone: "" });
  const [consent, setConsent] = useState(!presentation.sensitive);
  const [deleted, setDeleted] = useState(false);
  const [baseVersion, setBaseVersion] = useState(version);
  const [deleteOperationId, setDeleteOperationId] = useState(() => crypto.randomUUID());
  // One ID per attempted command preserves a retry after a lost response. Editing
  // the draft resets it so an altered body never reuses a committed operation ID.
  const [operationId, setOperationId] = useState(() => crypto.randomUUID());
  const refresh = () => client.invalidateQueries({ queryKey: savedDetailsKey(actorId) });
  const update = useMutation({ mutationFn: () => saveDetail(presentation.key, presentation.key === "emergency_contact" ? contact : typedValue(presentation.key, text), { operation_id: operationId, expected_version: baseVersion }), onSuccess: result => { setBaseVersion(result.version); setOperationId(crypto.randomUUID()); return refresh(); }, onError: error => { if (error instanceof StructuredApiError && error.status === 409) void refresh(); } });
  const remove = useMutation({ mutationFn: () => deleteDetail(presentation.key, { operation_id: deleteOperationId, expected_version: baseVersion }), onSuccess: result => { setBaseVersion(result.version); setDeleteOperationId(crypto.randomUUID()); setDeleted(true); setText(""); setContact({ name: "", relationship: "", phone: "" }); return refresh(); } });
  const pending = update.isPending || remove.isPending;
  const changed = () => { setOperationId(crypto.randomUUID()); update.reset(); setDeleted(false); };
  return <form className="grid gap-3 rounded-card border border-line p-4" onSubmit={event => { event.preventDefault(); update.mutate(); }}>
    {version !== baseVersion ? <div role="status"><p>This saved value changed. Your draft is still here.</p><button className="desk-button" type="button" onClick={() => { setText(textValue(saved?.value)); setContact(saved?.value && typeof saved.value === "object" && "name" in saved.value ? saved.value : { name: "", relationship: "", phone: "" }); setBaseVersion(version); changed(); }}>Review current saved value</button></div> : null}
    {presentation.key === "emergency_contact" ? <fieldset className="grid gap-3"><legend className="font-semibold text-ink">Emergency contact</legend>
      {(["name", "relationship", "phone"] as const).map(key => <Field key={key} label={key === "name" ? "Contact name" : key === "phone" ? "Contact phone" : "Relationship"}>
        <input className="desk-input" value={contact[key]} disabled={pending} onChange={e => { setContact({ ...contact, [key]: e.target.value }); changed(); }} />
      </Field>)}</fieldset> : <Field label={presentation.label} hint={presentation.sensitive ? "Sensitive · private to your account until you submit it to an event." : "Private saved detail. Your sign-in details and public profile stay separate."}>
        {presentation.multiline ? <textarea className="desk-input" value={text} disabled={pending} onChange={e => { setText(e.target.value); changed(); }} /> : <input className="desk-input" type={presentation.type || "text"} value={text} disabled={pending} onChange={e => { setText(e.target.value); changed(); }} />}
      </Field>}
    <label className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={consent} disabled={pending} onChange={e => { setConsent(e.target.checked); changed(); }} />Save to my private details</label>
    <div className="flex flex-wrap gap-2"><button className="desk-button-primary" disabled={pending || !consent} type="submit">Save {presentation.label.toLowerCase()}</button>
      {saved?.value != null ? <button className="desk-button-danger-outline" disabled={pending} type="button" onClick={() => remove.mutate()}>Delete {presentation.label.toLowerCase()}</button> : null}</div>
    {update.error || remove.error ? <p role="alert" className="text-danger">{(update.error || remove.error)?.message} Your draft is still here. Review current saved details before retrying.</p> : null}
    {update.isSuccess || deleted ? <p role="status" className="text-success-ink">{deleted ? "Saved detail deleted. Submitted event answers follow their event’s retention policy." : "Saved detail updated."}</p> : null}
  </form>;
}
