import { useEffect, useState } from "react";
import { useCardTemplate, useSaveCardTemplate } from "./api";
import type { CardTemplate } from "./types";

/** Keep the draft alive while the parent switches between the card workspace tabs. */
export function useCardTemplateDraft(makerspaceId: number) {
  const template = useCardTemplate(makerspaceId);
  const save = useSaveCardTemplate(makerspaceId);
  const [draft, setDraft] = useState<CardTemplate | null>(null);
  const [dirty, setDirty] = useState(false);

  // Seed once, and re-seed only while the form has no unsaved edits — otherwise a
  // background refetch would silently discard what the operator just typed.
  useEffect(() => {
    if (!template.data || dirty) return;
    setDraft(template.data);
  }, [template.data, dirty]);

  const patch = (changes: Partial<CardTemplate>) => {
    if (!draft) return;
    setDirty(true);
    setDraft({ ...draft, ...changes });
  };
  const toggleField = (field: string, checked: boolean) => {
    if (!draft) return;
    const next = checked
      ? [...draft.front_fields, field]
      : draft.front_fields.filter((value) => value !== field);
    patch({ front_fields: next });
  };

  return { template, save, draft, setDraft, dirty, setDirty, patch, toggleField };
}
