import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Receipt } from "lucide-react";

import { SegmentedControl } from "../../../components/ui";
import { SettingsEditorActions } from "../SettingsEditorActions";
import { usePriceDropCheck } from "../priceDrop/usePriceDropCheck";
import { PricingImpactDialog } from "./PricingImpactDialog";
import { PricingLendingFields } from "./PricingLendingFields";
import { PricingRateRows } from "./PricingRateRows";
import { RentalTimingControl } from "./RentalTimingControl";
import { REFUSALS, pricingApi, pricingError, pricingKeys, type PricingDefault, type PricingImpact } from "./pricingApi";
import { toDraft, toWrite, validateDraft, type DraftProblems, type PricingDraft } from "./pricingDraft";
import { workedExample } from "./pricingMath";

/** One area's rate card: free or paid, its rates, a live example, and save through the impact preview. */
export function PricingDomainCard({ makerspaceId, domain }: { makerspaceId: number; domain: string }) {
  const client = useQueryClient();
  const key = pricingKeys.card(makerspaceId, domain);
  const card = useQuery({ queryKey: key, queryFn: () => pricingApi.card(makerspaceId, domain) });
  const [draft, setDraft] = useState<PricingDraft | null>(null);
  const [problems, setProblems] = useState<DraftProblems>({});
  const [impact, setImpact] = useState<PricingImpact | null>(null);
  useEffect(() => { if (card.data) setDraft(toDraft(card.data)); }, [card.data]);

  const preview = useMutation({
    mutationFn: (data: PricingDefault) => pricingApi.impact(makerspaceId, domain, toWrite(data, draft!)),
    onSuccess: setImpact,
  });
  const save = useMutation({
    mutationFn: (data: PricingDefault) => pricingApi.save(makerspaceId, domain, toWrite(data, draft!)),
    onSuccess: data => { client.setQueryData(key, data); setImpact(null); },
  });
  const drop = usePriceDropCheck(makerspaceId);

  if (card.isLoading) return <LogoLoader label={t`Loading prices…`} size={48} className="min-h-16 py-3" />;
  if (card.error) return <p role="alert" className="text-sm text-danger">{pricingError(card.error)}</p>;
  if (!card.data || !draft) return null;
  const data = card.data;
  const readOnlyArea = data.lines.every(line => line.read_only);
  const disabled = !data.editable || readOnlyArea || preview.isPending || save.isPending;
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(data));
  const example = workedExample(domain, draft, data.currency);
  const update = (patch: Partial<PricingDraft>) => { setDraft({ ...draft, ...patch }); save.reset(); };
  const submit = () => {
    const next = validateDraft(data, draft);
    setProblems(next);
    if (!Object.keys(next).length) preview.mutate(data);
  };
  // Lane L24: a lower booking or machine rate may owe paid, not-yet-used items a refund.
  const confirmSave = async () => {
    if (domain === "bookings" || domain === "machines") {
      setImpact(null);
      const path = `/admin/makerspace/${makerspaceId}/pricing/${domain}`;
      if (!(await drop.check(path, "PUT", toWrite(data, draft)))) return;
    }
    save.mutate(data);
  };

  return <div className="grid min-w-0 gap-4">
    {!data.editable && !readOnlyArea ? <p className="rounded-xl border border-line bg-surface p-3 text-sm text-ink">
      {t`You can see these prices but not change them. `}{REFUSALS[data.refusal ?? ""] ?? t`Only the Space Manager can change them.`}</p> : null}
    {data.editable && data.locked ? <p className="text-xs text-muted">{t`Locked: only the Space Manager can change these prices.`}</p> : null}
    {readOnlyArea ? <p className="text-sm text-muted">{t`Membership prices are set on each plan and the joining fee in membership settings. They are shown here for reference.`}</p> : <div className="grid gap-2">
      <span className="text-sm font-semibold text-ink">{t`Is ${data.label.toLowerCase()} free or paid?`}</span>
      {disabled ? <p className="text-sm text-ink">{draft.mode === "free" ? t`Free` : t`Paid`}</p>
        : <SegmentedControl label={t`${data.label}: free or paid`} value={draft.mode}
          options={[{ value: "free", label: t`Free` }, { value: "paid", label: t`Paid` }]}
          onChange={value => update({ mode: value as PricingDraft["mode"] })} />}
      {draft.mode === "free" ? <p className="text-xs text-muted">{t`Free: the rates below are kept but nothing is charged. Items with their own price still charge it.`}</p> : null}
    </div>}
    <PricingRateRows card={data} lines={draft.lines} problems={problems} disabled={disabled}
      onChange={(component, patch) => update({ lines: draft.lines.map(line => line.component === component ? { ...line, ...patch } : line) })} />
    {draft.lending ? <PricingLendingFields lending={draft.lending} currency={data.currency} problems={problems} disabled={disabled}
      onChange={patch => update({ lending: { ...draft.lending!, ...patch } })} /> : null}
    {domain === "machines" ? <p className="text-sm text-muted">{t`Failed jobs: free by default.`}</p> : null}
    {example ? <aside aria-live="polite" aria-label={t`Worked example`} className="grid gap-1 rounded-xl border border-line bg-panel p-4 text-sm">
      <p className="flex items-center gap-2 font-semibold text-ink"><Receipt aria-hidden="true" size={16} />{example.lead}</p>
      {example.notes.map(note => <p key={note} className="text-muted">{note}</p>)}
      <p className="text-xs text-muted">{t`Before tax and member discounts.`}</p>
    </aside> : null}
    {domain === "loans" ? <RentalTimingControl makerspaceId={makerspaceId} /> : null}
    {data.editable && !readOnlyArea ? <div className="flex flex-wrap items-center gap-2">
      <SettingsEditorActions dirty={dirty} pending={preview.isPending || save.isPending} disabled={disabled}
        onSave={submit} onDiscard={() => { setDraft(toDraft(data)); setProblems({}); preview.reset(); save.reset(); }} />
      {save.isSuccess ? <span role="status" className="text-xs text-muted">{t`Prices saved.`}</span> : null}
    </div> : null}
    {Object.keys(problems).length ? <p role="alert" className="text-sm text-danger">
      {t`Some prices need fixing. Check the messages above, then save again.`}</p> : null}
    {preview.error ? <p role="alert" className="text-sm text-danger">{pricingError(preview.error)}</p> : null}
    {save.error && !impact ? <p role="alert" className="text-sm text-danger">{pricingError(save.error)}</p> : null}
    {impact ? <PricingImpactDialog impact={impact} areaLabel={data.label} pending={save.isPending || drop.checking}
      error={save.error ? pricingError(save.error) : null} onConfirm={() => { void confirmSave(); }}
      onClose={() => { setImpact(null); save.reset(); }} /> : null}
    {drop.dialog}
  </div>;
}
