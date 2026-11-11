import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";
import { personalRecipientKey } from "./personalQueryKeys";
import { channelLabel } from "./channelCatalog";
import { familyLabel } from "./notificationFamilies";
import { notificationEventLabel } from "./notificationEventLabels";

type Cell = { daily_digest?: boolean; feature: string; channel: string; enabled: boolean; available: boolean; mandatory_events: string[] };
type Preferences = { cells: Cell[] };

export function PreferenceCentre({ makerspaceId, digests = false }: { makerspaceId: number; digests?: boolean }) {
  const client = useQueryClient();
  const key = ["notifications-preferences", makerspaceId, personalRecipientKey()];
  const path = `/notifications/preferences/${makerspaceId}`;
  const preferences = useQuery({ queryKey: key, queryFn: () => memberRequest<Preferences>(path) });
  const save = useMutation({ mutationFn: async (cell: Cell & { changeDigest?: boolean }) => {
    const recipientKey = key;
    const data = await memberRequest<Preferences>(path, {
      method: "PATCH", body: JSON.stringify({ feature: cell.feature, channel: cell.channel, enabled: cell.changeDigest ? cell.enabled : !cell.enabled, ...(cell.changeDigest ? { daily_digest: !cell.daily_digest } : {}) }),
    });
    return { data, recipientKey };
  }, onSuccess: ({ data, recipientKey }) => client.setQueryData(recipientKey, data) });
  const error = preferences.error ?? save.error;
  return <section className="desk-panel p-5">
    <h2 className="title-panel">{t`Communication preferences`}</h2>
    <p className="mt-2 text-sm text-muted">{t`Choose optional messages for each family and personal channel. Safety and account recovery emails always remain enabled. Makerspace channel switches still apply.`}</p>
    {preferences.isLoading ? <p className="mt-3 text-sm text-muted">{t`Loading preferences...`}</p> : null}
    {error ? <p className="mt-3 text-sm text-danger" role="alert">{error.message}</p> : null}
    {/* Each card stacks its title over its switches at every width: a side-by-side
        label/control row inside a half-width card squeezed both to a sliver on tablets. */}
    <div className="mt-3 grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">{preferences.data?.cells.map((cell) => <fieldset key={`${cell.feature}:${cell.channel}`}
      className="min-w-0 rounded-md border border-line p-3 text-sm">
      <legend className="title-section float-left mb-1 w-full break-words">{`${familyLabel(cell.feature)} · ${channelLabel(cell.channel)}`}</legend><label className="flex min-h-11 items-center gap-3"><input className="h-5 w-5 shrink-0" type="checkbox" aria-label={t`${familyLabel(cell.feature)} messages by ${channelLabel(cell.channel)}`} checked={cell.enabled} disabled={save.isPending || (!cell.available && !cell.enabled)}
        onChange={() => save.mutate(cell)} />
      <span>{t`Send me these messages`}{!cell.available ? <span className="block text-xs text-muted">{t`Disabled by makerspace`}</span> : null}
        {cell.mandatory_events.length ? <span className="block text-xs text-muted">{t`Safety emails stay enabled: ${cell.mandatory_events.map(notificationEventLabel).join(", ")}`}</span> : null}
      </span></label>
      {digests && cell.channel === "email" ? <label className="flex min-h-11 items-center gap-3 text-sm"><input className="h-5 w-5 shrink-0" type="checkbox" aria-label={t`${cell.feature} daily digest`} checked={cell.daily_digest ?? false} disabled={save.isPending || !cell.enabled || !cell.available} onChange={() => save.mutate({ ...cell, changeDigest: true })} /> {t` Daily digest for optional emails`}</label> : null}
    </fieldset>)}</div>
  </section>;
}
