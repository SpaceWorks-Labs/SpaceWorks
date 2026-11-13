import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { ActionControl, Field } from "../../components/ui";
import { presenceErrorText } from "../presence/presenceCopy";
import { anthiasKeys, NOW_SECTIONS, nowConfigApi, type NowConfig, type NowSection } from "./anthiasApi";
import type { DisplayPrivacy } from "./api";
import { privacyLabel } from "./DisplayConfigFields";
import { PanelOrderEditor } from "./PanelOrderEditor";

export const nowSectionLabel = (key: NowSection): string => ({ here_now: t`Here now`, machines: t`Machines now`, events: t`Events calendar`,
  public_stats: t`Public stats`, opening_hours: t`Opening hours` })[key];

function Form({ makerspaceId, initial }: { makerspaceId: number; initial: NowConfig }) {
  const client = useQueryClient();
  const [sections, setSections] = useState(initial.sections);
  const [privacy, setPrivacy] = useState<DisplayPrivacy>(initial.privacy);
  const [refresh, setRefresh] = useState(String(initial.refresh_seconds));
  const save = useMutation({ mutationFn: () => nowConfigApi.put(makerspaceId, { sections, privacy, refresh_seconds: Number(refresh) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: anthiasKeys.nowConfig(makerspaceId) }) });
  return <div className="grid gap-3 sm:grid-cols-2">
    <PanelOrderEditor legend={t`Sections, in order`} all={NOW_SECTIONS} value={sections} label={nowSectionLabel} onChange={setSections} />
    <div className="grid content-start gap-3">
      <Field label={t`Who Here now shows`} hint={t`Never shows more than a visitor could see before.`}>
        <select className="desk-input" value={privacy} onChange={(e) => setPrivacy(e.target.value as DisplayPrivacy)}>
          {(["profiles", "first_names", "counts"] as const).map((p) => <option key={p} value={p}>{privacyLabel(p)}</option>)}</select></Field>
      <Field label={t`Refresh every (seconds)`} hint={t`Between 10 and 600.`}>
        <input className="desk-input" inputMode="numeric" value={refresh} onChange={(e) => setRefresh(e.target.value.replace(/\D/g, ""))} /></Field>
    </div>
    {save.error ? <p role="alert" className="text-sm text-danger sm:col-span-2">{presenceErrorText(save.error).text}</p> : null}
    <div><ActionControl primary action={{ label: t`Save page settings`, pending: save.isPending, onClick: () => save.mutate() }} /></div>
  </div>;
}

/** The space's public "now" page: which sections show, in what order, and how private Here now is. */
export function PublicPageSettings({ makerspaceId }: { makerspaceId: number }) {
  const query = useQuery({ queryKey: anthiasKeys.nowConfig(makerspaceId), queryFn: () => nowConfigApi.get(makerspaceId) });
  return <div className="grid gap-3">
    <h3 className="text-base font-semibold">{t`Public page sections`}</h3>
    <p className="text-sm text-muted">{t`What the space's public page shows about right now. A section also needs its own module to be on.`}</p>
    {query.isError ? <p role="alert" className="text-sm text-danger">{presenceErrorText(query.error).text}</p> : null}
    {query.data ? <Form key={JSON.stringify(query.data)} makerspaceId={makerspaceId} initial={query.data} /> : null}
  </div>;
}
