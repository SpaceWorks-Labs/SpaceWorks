import { t } from "@lingui/core/macro";
import { SettingsQueryState } from "./SettingsQueryState";
import { SettingsRow } from "../../components/ui";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { useScopeOptions } from "./NotificationDestinations";
import { EventRecipients } from "./NotificationRecipientEvent";
import type { RecipientRulesResponse } from "./notificationDestinationTypes";
import { notificationEventLabel } from "../notifications/notificationEventLabels";
import { LogoLoader } from "../../components/LogoLoader";

const FEATURE_LABELS: Record<string, string> = {
  events: t`Events`,
  bookings: t`Bookings`,
  maintenance: t`Maintenance`,
  devices: t`Devices`,
  members: t`Members`,
  payments: t`Payments`,
  stock: t`Stock and procurement`,
  certifications: t`Machine access`,
  // Decision 343: which staff get machine-service job notices (the `printing` family is machine service's).
  printing: t`Machine service jobs`,
};

const RECIPIENTS_KEY = (makerspaceId: number) =>
  ["notification-recipient-rules", makerspaceId] as const;

/** Who hears about one lifecycle event. Empty means the action-based default. */
export function NotificationRecipientPicker({
  makerspaceId,
  delegated = false,
  visible = true,
}: {
  makerspaceId: number;
  delegated?: boolean;
  visible?: boolean;
}) {
  const path = `/admin/makerspace/${makerspaceId}/notification-recipient-rules`;
  const data = useQuery({
    queryKey: RECIPIENTS_KEY(makerspaceId),
    queryFn: () => staffRequest<RecipientRulesResponse>(path),
  });
  const [selected, setSelected] = useState<{ feature: string; event: string } | null>(null);
  const broadOptions = useScopeOptions(makerspaceId, !delegated);
  const options = delegated && data.data
    ? {
        machineTypes: data.data.scope_options?.machine_types ?? [],
        machines: data.data.scope_options?.machines ?? [],
        categories: data.data.scope_options?.categories ?? [],
      }
    : broadOptions;
  const features = data.data?.features ?? [];
  const current = selected ?? (features[0]
    ? { feature: features[0].key, event: features[0].events[0] }
    : null);
  const events = features.find((item) => item.key === current?.feature)?.events ?? [];
  if (!visible) return null;

  return (
    <section className="mt-6" aria-labelledby="notification-recipients-heading"><h3 id="notification-recipients-heading" className="title-section">{t`Who gets notified`}</h3>
    <SettingsQueryState query={data} resource={t`recipient`}><SettingsRow label={t`Recipients`} helper={t`Which staff get each kind of alert.`}><div className="@container min-w-0">

      <p className="mt-2 text-sm text-muted">
        {delegated
          ? t`Pick recipients for maintenance alerts within your machine scope. Every rule must name at least one reachable machine or machine type.`
          : t`Pick recipients per event. Leave an event empty to notify everyone whose role covers it, which is the default. A member who has turned notifications off is never mailed, even when selected.`}
      </p>

      {data.isLoading ? <LogoLoader label={t`Loading…`} size={48} className="min-h-16 py-3" /> : null}
      {!data.isLoading && features.length === 0 ? (
        <p className="mt-3 text-sm text-muted">
          {t`None of the modules with selectable recipients are installed.`}</p>
      ) : null}

      {current ? (
        <>
          <div className="mt-3 grid gap-2 @md:grid-cols-2">
            <label className="grid gap-1 text-sm">
              <span className="eyebrow">{t`Area`}</span>
              <select
                className="desk-input"
                onChange={(changed) => {
                  const feature = changed.target.value;
                  const first = features.find((item) => item.key === feature)?.events[0] ?? "";
                  setSelected({ feature, event: first });
                }}
                value={current.feature}
              >
                {features.map((feature) => (
                  <option key={feature.key} value={feature.key}>
                    {FEATURE_LABELS[feature.key] ?? feature.key}
                  </option>
                ))}
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="eyebrow">{t`Event`}</span>
              <select
                className="desk-input"
                onChange={(changed) =>
                  setSelected({ feature: current.feature, event: changed.target.value })
                }
                value={current.event}
              >
                {events.map((event) => (
                  <option key={event} value={event}>{notificationEventLabel(event)}</option>
                ))}
              </select>
            </label>
          </div>

          {data.data ? (
            <EventRecipients
              data={data.data}
              delegated={delegated}
              event={current.event}
              feature={current.feature}
              makerspaceId={makerspaceId}
              options={options}
              path={path}
            />
          ) : null}
        </>
      ) : null}
    </div></SettingsRow></SettingsQueryState></section>
  );
}
