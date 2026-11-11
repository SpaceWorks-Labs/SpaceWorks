// Staff-card numbering: its own prefix and pattern (apps/card_designs/staff_card_numbering.py), separate from
// member cards. Applies at once to the next card issued. An empty pattern restores STF-0001.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";

import { NumberPatternFields } from "../../../../components/card-designer/NumberPatternFields";
import { STAFF_TOKENS, patternProblem } from "../../../../components/card-designer/numberPattern";
import { Callout, ErrorBlock, Skeleton } from "../../../../components/ui";
import { useSaveStaffCardSettings, useStaffCardSettings } from "./api";

export function StaffNumbering({ makerspaceId }: { makerspaceId: number }) {
  const settings = useStaffCardSettings(makerspaceId);
  const save = useSaveStaffCardSettings(makerspaceId);
  const [draft, setDraft] = useState({ prefix: "", pattern: "" });
  useEffect(() => { if (settings.data) setDraft({ prefix: settings.data.prefix, pattern: settings.data.pattern }); }, [settings.data]);
  if (settings.isLoading) return <Skeleton className="h-40 w-full" />;
  if (settings.isError || !settings.data) return <ErrorBlock error={settings.error} resource={t`staff card numbering`} onRetry={() => void settings.refetch()} />;
  const saved = settings.data;
  const changed = draft.prefix !== saved.prefix || draft.pattern !== saved.pattern;
  const invalid = Boolean(patternProblem(draft.prefix, draft.pattern, STAFF_TOKENS));

  return <div className="grid max-w-2xl gap-4">
    <section className="grid gap-3 rounded-card border border-line bg-panel p-4" aria-label={t`Staff card numbering`}>
      <h3 className="text-sm font-semibold text-ink">{t`Staff card numbers`}</h3>
      <NumberPatternFields prefix={draft.prefix} pattern={draft.pattern} tokens={STAFF_TOKENS} onChange={setDraft} />
      <p className="text-xs text-muted">{t`Now issuing: ${saved.preview.join(", ")}. Cards already issued keep their number.`}</p>
      {save.error ? <ErrorBlock error={save.error} /> : null}
      <button type="button" className="desk-button-primary min-h-11 w-fit" disabled={!changed || invalid || save.isPending}
        onClick={() => save.mutate(draft)}>{save.isPending ? t`Saving…` : t`Save numbering`}</button>
    </section>
    <Callout size="inline" tone={saved.auto_issue ? "success" : "warn"}
      lead={saved.auto_issue ? t`Cards are issued automatically when a staff role is granted.` : t`Cards are issued by hand. Switch on automatic issue under Features.`} />
  </div>;
}
