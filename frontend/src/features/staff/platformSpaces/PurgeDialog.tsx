import { useState } from "react";
import { Field } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { ActionDialog } from "./ActionDialog";
import { useSpaceAction, type HealthCard } from "./spacesApi";

/** Purge deletes an archived space for good, so the slug must be typed out to confirm. */
export function PurgeDialog({ card, onClose }: { card: HealthCard; onClose: () => void }) {
  const [slug, setSlug] = useState("");
  const mutation = useSpaceAction<void>(card.id, "purge", () => { toast(`${card.name} was purged.`); onClose(); });
  return <ActionDialog title="Purge this space" tone="danger" confirmLabel="Purge for good" pending={mutation.isPending}
    error={mutation.error} canSubmit={slug.trim() === card.slug} onCancel={onClose}
    message={<>Every record, file and account link of <strong className="text-ink">{card.name}</strong> is deleted. This cannot be undone.</>}
    onSubmit={() => mutation.mutate({ confirm_slug: slug.trim() })}>
    <Field label={`Type ${card.slug} to confirm`}>
      <input className="desk-input" autoComplete="off" autoCapitalize="none" spellCheck={false} value={slug} onChange={event => setSlug(event.target.value)} />
    </Field>
  </ActionDialog>;
}
