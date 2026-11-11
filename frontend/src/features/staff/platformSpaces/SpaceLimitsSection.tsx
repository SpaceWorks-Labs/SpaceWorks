import { t } from "@lingui/core/macro";
import { useMemo, useState } from "react";
import { ErrorText, Skeleton } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { draftValue, LimitRowView } from "./LimitRowView";
import { buildOverrides, groupLimits, toInput, unifyLimits, validInput } from "./limitsModel";
import { useSaveSpaceLimits, useSpaceLimits, type SpaceLimits } from "./limitsApi";

/**
 * Every limit of one space, grouped by area (decisions 281, 284): usage bar, the value (blank = no
 * limit, the default), Reset to none, and one Save that sends the complete override map (the server
 * asks for a recent sign-in first). Rows are rendered from the payload, never from a frontend key list.
 */
export function SpaceLimitsEditor({ id, data, headingLevel = 4 }: { id: number; data: SpaceLimits; headingLevel?: 3 | 4 }) {
  const save = useSaveSpaceLimits(id);
  const rows = useMemo(() => unifyLimits(data), [data]);
  const groups = useMemo(() => groupLimits(rows, data.areas), [rows, data.areas]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [domain, setDomain] = useState(data.custom_domain);
  const Heading = headingLevel === 3 ? "h3" : "h4";
  const invalid = Object.values(drafts).some(value => !validInput(value));
  const dirty = domain !== data.custom_domain || rows.some(row => drafts[row.key] !== undefined && drafts[row.key].trim() !== toInput(row, row.stored));
  const anySet = rows.some(row => row.editable && draftValue(row, drafts).trim() !== "");
  const set = (key: string, value: string) => setDrafts(current => ({ ...current, [key]: value }));
  const submit = () => save.mutate(buildOverrides(rows, drafts, domain), {
    onSuccess: () => { setDrafts({}); toast(t`Limits saved.`); },
  });
  return <div className="grid gap-5">
    {groups.map(group => <section key={group.key} aria-labelledby={`limits-${id}-${group.key}`} className="grid gap-1">
      <Heading id={`limits-${id}-${group.key}`} className="title-section">{group.label}</Heading>
      <ul className="grid">{group.rows.map(row => <LimitRowView key={row.key} row={row} value={draftValue(row, drafts)}
        disabled={save.isPending} onChange={value => set(row.key, value)} />)}</ul>
    </section>)}
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" className="h-4 w-4" checked={domain} disabled={save.isPending} onChange={event => setDomain(event.target.checked)} />
      {t`Allow this space to use its own domain name`}
    </label>
    <p className="text-xs text-muted">{t`Every limit starts as no limit. Enter a number to set one for this space; leave it empty (Reset to none) for no limit of its own. A hosted space's plan applies where it sets a value; -1 means no limit even then. Limits only stop something new: reading, exporting, paying existing charges, refunds and returns always work.`}</p>
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
    <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button-primary min-h-11" disabled={invalid || !dirty || save.isPending} onClick={submit}>
        {save.isPending ? t`Saving…` : t`Save limits`}</button>
      {anySet ? <button type="button" className="desk-button-ghost min-h-11" disabled={save.isPending}
        onClick={() => setDrafts(Object.fromEntries(rows.filter(row => row.editable).map(row => [row.key, ""])))}>{t`Reset every limit to none`}</button> : null}
      {dirty ? <button type="button" className="desk-button-ghost min-h-11" disabled={save.isPending}
        onClick={() => { setDrafts({}); setDomain(data.custom_domain); }}>{t`Discard changes`}</button> : null}
    </div>
  </div>;
}

/** Per-space limits with usage, in the space's detail drawer and on its limits page. A load error says so, with a retry (LM-4). */
export function SpaceLimitsSection({ makerspaceId, headingLevel = 3 }: { makerspaceId: number; headingLevel?: 2 | 3 }) {
  const limits = useSpaceLimits(makerspaceId);
  if (limits.isLoading) return <Skeleton className="h-24 w-full" />;
  if (limits.isError || !limits.data || !Array.isArray(limits.data.rows)) {
    return <ErrorText resource={t`limits`} onRetry={() => { void limits.refetch(); }} />;
  }
  const data = limits.data;
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const hasRows = data.rows.length + (data.platform_rows?.length ?? 0) + (data.quota_rows?.length ?? 0) > 0;
  return <section aria-labelledby={`space-limits-${makerspaceId}`} className="grid gap-3">
    <Heading id={`space-limits-${makerspaceId}`} className="title-panel">{t`Limits`}</Heading>
    {data.hosted === false ? <p className="text-sm text-muted"><strong className="text-ink">{t`Unlimited (own space).`}</strong>{" "}
      {t`No plan applies to an own space. A limit you set below still applies to it.`}</p> : null}
    {hasRows ? <SpaceLimitsEditor key={JSON.stringify(data)} id={makerspaceId} data={data} headingLevel={headingLevel === 2 ? 3 : 4} /> : null}
  </section>;
}
