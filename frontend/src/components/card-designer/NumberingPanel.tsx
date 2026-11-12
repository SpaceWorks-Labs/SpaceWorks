// Member-card numbering for one design target: the space default, or one title. The draft is saved at once
// but only reaches issued cards when the design is published (approved), so the panel says so while pending.
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { Badge, ErrorBlock } from "../ui";
import { NumberPatternFields } from "./NumberPatternFields";
import { MEMBER_TOKENS, patternProblem } from "./numberPattern";
import { LogoLoader } from "../LogoLoader";
import { BoxArt } from "../BoxSpinner";

type Scheme = { title_id: number | null; prefix: string; pattern: string; draft_prefix: string; draft_pattern: string;
  pending: boolean; published_at: string | null; preview: string[] };
type Schemes = { default: Scheme; titles: Scheme[] };

const path = (makerspaceId: number) => `/admin/makerspaces/${makerspaceId}/card-number-schemes`;
const key = (makerspaceId: number) => ["card-number-schemes", makerspaceId] as const;

export function NumberingPanel({ makerspaceId, titleId, canEdit }: { makerspaceId: number; titleId: number | null; canEdit: boolean }) {
  const client = useQueryClient();
  const schemes = useQuery({ queryKey: key(makerspaceId), queryFn: () => staffRequest<Schemes>(path(makerspaceId)) });
  const scheme = titleId === null ? schemes.data?.default : schemes.data?.titles.find((row) => row.title_id === titleId);
  const [draft, setDraft] = useState({ prefix: "", pattern: "" });
  useEffect(() => { setDraft({ prefix: scheme?.draft_prefix ?? "", pattern: scheme?.draft_pattern ?? "" }); },
    [scheme?.draft_prefix, scheme?.draft_pattern, titleId]);
  const save = useMutation({
    mutationFn: () => staffRequest<Scheme>(titleId === null ? path(makerspaceId) : `${path(makerspaceId)}/titles/${titleId}`,
      { method: "PUT", body: JSON.stringify(draft) }),
    onSuccess: () => client.invalidateQueries({ queryKey: key(makerspaceId) }),
  });
  if (schemes.isLoading) return <LogoLoader size={48} className="min-h-32 py-3" />;
  if (schemes.isError) return <ErrorBlock error={schemes.error} resource={t`card numbering`} onRetry={() => void schemes.refetch()} />;
  const changed = draft.prefix !== (scheme?.draft_prefix ?? "") || draft.pattern !== (scheme?.draft_pattern ?? "");
  const invalid = Boolean(patternProblem(draft.prefix, draft.pattern, MEMBER_TOKENS));

  return <section className="grid gap-3 rounded-card border border-line bg-panel p-4" aria-label={t`Card numbering`}>
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="text-sm font-semibold text-ink">{titleId === null ? t`Card numbering for this space` : t`Card numbering for this title`}</h3>
      {scheme?.pending ? <Badge tone="warn">{t`Draft: goes live when this design is published`}</Badge> : null}
    </div>
    <NumberPatternFields prefix={draft.prefix} pattern={draft.pattern} tokens={MEMBER_TOKENS} readOnly={!canEdit} onChange={setDraft} />
    {scheme && scheme.published_at && (scheme.prefix || scheme.pattern) ? <p className="text-xs text-muted">{t`Live now: ${scheme.pattern || "—"}`}</p> : null}
    {save.error ? <ErrorBlock error={save.error} /> : null}
    {canEdit ? <button type="button" className="desk-button-primary min-h-11 w-fit" disabled={!changed || invalid || save.isPending}
      onClick={() => save.mutate()}>{save.isPending ? <><BoxArt size={16} mono />{t`Saving…`}</> : t`Save draft`}</button> : null}
  </section>;
}
