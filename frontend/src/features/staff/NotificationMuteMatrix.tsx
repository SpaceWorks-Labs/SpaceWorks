import { SettingsQueryState } from "./SettingsQueryState";
import { NotificationMuteTable } from "./NotificationMuteTable";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { NotificationChannelPreferences } from "./NotificationChannelPreferences";
import type {
  MuteChange,
  NotificationFeature,
  NotificationRulesResponse,
  RuleCatalogEntry,
  RuleMute,
} from "./notificationRuleTypes";

export function NotificationMuteMatrix({ makerspaceId }: { makerspaceId: number }) {
  const queryClient = useQueryClient();
  const path = `/admin/makerspace/${makerspaceId}/notification-rules`;
  const queryKey = ["notification-rules", makerspaceId] as const;

  const rules = useQuery({
    queryKey,
    queryFn: () => staffRequest<NotificationRulesResponse>(path),
  });

  const updateMute = useMutation({
    mutationFn: (change: MuteChange) =>
      staffRequest<NotificationRulesResponse>(path, {
        method: "PATCH",
        body: JSON.stringify({ changes: [change] }),
      }),
    onMutate: async (change) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<NotificationRulesResponse>(queryKey);
      queryClient.setQueryData<NotificationRulesResponse>(queryKey, (current) =>
        current ? { ...current, mutes: applyMuteChange(current.mutes, change) } : current,
      );
      return { previous };
    },
    onError: (_error, _change, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(queryKey, context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  if (rules.isLoading) {
    return <SettingsQueryState query={rules} resource="mute matrix" />;
  }

  if (rules.error) {
    return <SettingsQueryState query={rules} resource="mute matrix" />;
  }

  if (!rules.data) return null;

  return (
    <SettingsQueryState query={rules} resource="mute matrix"><div className="mt-4 grid min-w-0 gap-6">
      <NotificationChannelPreferences makerspaceId={makerspaceId} rules={rules.data} />
      {/* Full width like the channel matrix above: a half-width settings row squeezed these
          recipient-by-event tables into a sideways scroll from tablet up. */}
      <section aria-labelledby={`advanced-mutes-${makerspaceId}`} className="grid min-w-0 gap-4">
        <div>
          <h4 id={`advanced-mutes-${makerspaceId}`} className="text-sm font-semibold text-ink">Advanced email recipient/event mutes</h4>
          <p className="mt-2 max-w-prose text-sm text-muted">Checked = muted for that individual email recipient and event. These mutes apply only while the matching feature&apos;s Email channel above is enabled. Return reminders cannot be individually muted.</p>
        </div>
        <div className="grid min-w-0 gap-4">
          {rules.data.catalog.map((entry) => {
            const emailEnabled = isEmailEnabled(entry, rules.data);
            const disabledMessageId = `email-disabled-${entry.stream}-${entry.audience}`;
            return (
              <section
                key={`${entry.stream}:${entry.audience}`}
                className="min-w-0 rounded-md border border-line bg-surface p-3"
              >
                <h5 className="text-sm font-semibold text-ink">
                  {streamLabel(entry.stream)} &middot; {audienceLabel(entry.audience)}
                </h5>
                {!emailEnabled ? (
                  <p id={disabledMessageId} className="mt-2 text-xs text-warn-ink">
                    Advanced mutes are read-only while this feature&apos;s Email channel is disabled.
                  </p>
                ) : null}
                <NotificationMuteTable entry={entry} mutes={rules.data.mutes} emailEnabled={emailEnabled}
                  disabledMessageId={disabledMessageId} pending={updateMute.isPending} onChange={change => updateMute.mutate(change)} />
              </section>
            );
          })}
        </div>
        {updateMute.error ? (
          <p className="mt-3 text-sm text-danger" role="alert" aria-live="assertive">
            {updateMute.error.message}
          </p>
        ) : null}
      </section>
    </div></SettingsQueryState>
  );
}

function isEmailEnabled(entry: RuleCatalogEntry, rules: NotificationRulesResponse) {
  const feature = featureForEntry(entry, rules.features);
  if (!feature) return true;
  return (
    rules.preferences.find(
      (cell) => cell.feature === feature.key && cell.channel === "email",
    )?.enabled ?? true
  );
}

function featureForEntry(entry: RuleCatalogEntry, features: NotificationFeature[]) {
  const aliases: Record<string, string> = {
    hardware: "hardware_requests",
    hardware_request: "hardware_requests",
    hardware_requests: "hardware_requests",
    print: "printing",
    printing: "printing",
  };
  const expectedKey = aliases[entry.stream] ?? entry.stream;
  return (
    features.find((feature) => feature.key === expectedKey) ??
    features.find((feature) =>
      entry.events.some((eventName) => feature.events.includes(eventName)),
    )
  );
}

function applyMuteChange(mutes: RuleMute[], change: MuteChange) {
  const withoutCurrent = mutes.filter((mute) => !matchesMute(mute, change));
  return change.muted ? [...withoutCurrent, change] : withoutCurrent;
}

function matchesMute(mute: RuleMute, candidate: RuleMute) {
  return (
    mute.target === candidate.target &&
    mute.stream === candidate.stream &&
    mute.event === candidate.event &&
    mute.audience === candidate.audience
  );
}

function streamLabel(stream: string) {
  return humanize(stream);
}

function audienceLabel(audience: string) {
  if (audience === "requester") return "Requester emails";
  if (audience === "staff") return "Staff emails";
  return `${humanize(audience)} emails`;
}

function humanize(value: string) {
  const label = value.replace(/_/g, " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
