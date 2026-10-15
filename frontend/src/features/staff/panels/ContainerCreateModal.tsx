import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ErrorText, Field, Modal } from "../../../components/ui";
import { staffRequest } from "../../../lib/api";
import { invalidateContainerViews, invalidateQrViews } from "../queryInvalidation";
import type { Container } from "./ContainersPanel";

/** POST /admin/qr/boxes creates the box and its QR label in one step (apps/boxes CreateBoxQrView). */
export function ContainerCreateModal({ makerspaceId, open, onClose, onCreated }: { makerspaceId: number; open: boolean; onClose: () => void; onCreated: (container: Container) => void }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState("");
  const [location, setLocation] = useState("");
  const [description, setDescription] = useState("");
  const reset = () => { setLabel(""); setLocation(""); setDescription(""); create.reset(); };
  const create = useMutation({
    mutationFn: () => staffRequest<Container>("/admin/qr/boxes", { method: "POST",
      body: JSON.stringify({ makerspace_id: makerspaceId, label: label.trim(), location: location.trim(), description: description.trim() }) }),
    onSuccess: (created) => {
      invalidateContainerViews(queryClient, makerspaceId);
      invalidateQrViews(queryClient, makerspaceId);
      reset();
      onCreated(created);
    },
  });
  const close = () => { if (!create.isPending) { reset(); onClose(); } };
  return <Modal open={open} onClose={close} title="New container" footer={<div className="desk-actions flex flex-wrap justify-end gap-2">
    <button className="desk-button-ghost" type="button" disabled={create.isPending} onClick={close}>Cancel</button>
    <button className="desk-button-primary" type="submit" form="container-create" disabled={create.isPending || !label.trim()}>{create.isPending ? "Creating…" : "Create container"}</button>
  </div>}>
    <form id="container-create" className="grid gap-4" onSubmit={event => { event.preventDefault(); if (label.trim()) create.mutate(); }}>
      <p className="text-sm text-muted">A QR label is created with it. Print it from QR labels.</p>
      <Field label="Label"><input className="desk-input" value={label} onChange={event => setLabel(event.target.value)} /></Field>
      <Field label="Location (optional)"><input className="desk-input" value={location} onChange={event => setLocation(event.target.value)} /></Field>
      <Field label="Description (optional)"><textarea className="desk-input min-h-20" value={description} onChange={event => setDescription(event.target.value)} /></Field>
      <ErrorText message={create.error?.message} />
    </form>
  </Modal>;
}
