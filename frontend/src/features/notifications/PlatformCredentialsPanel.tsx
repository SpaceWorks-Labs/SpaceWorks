import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { ConfirmDialog, ErrorText, StatusPill } from "../../components/ui";
import { staffRequest } from "../../lib/api";
import { spacePlanKey, useSpacePlanUsage, type PlatformSwitch, type UsageRow } from "../staff/hostingPlan/spacePlanApi";
import { limitAmount } from "../staff/platformSpaces/LimitRowView";
import { walletCredentialsApi, walletKeys } from "../walletCredentials/api";
import { channelSpecs, defaultChannel } from "./channelCatalog";
import { useChannels, type Channel, type ChannelKey } from "./channelsApi";

type Row = { key: PlatformSwitch; label: string; usageKey: string; own: boolean | null; ownHint: string; section?: string };
const USAGE_KEY: Record<PlatformSwitch, string> = { email: "platform_email_monthly", sms: "platform_sms_monthly",
  whatsapp: "platform_whatsapp_monthly", native_push: "platform_push_monthly", wallet: "platform_wallet_monthly" };

/** Platform use this month in words: "12 of 500" or "12 · no limit". */
function usageText(row?: UsageRow) {
  if (!row || row.used === null) return null;
  return row.limit === null ? t`Platform use this month: ${limitAmount(row, row.used)} · no limit`
    : t`Platform use this month: ${limitAmount(row, row.used)} of ${limitAmount(row, row.limit)}`;
}

/**
 * Settings › Communication (decision 281): per integration, whether the platform's credentials may serve
 * this space when it has none of its own (on by default), whether its own are saved (never shown), and
 * how much of the platform's monthly allowance it used. Its own credentials always win and are never
 * limited; with the switch off and no own credentials that channel is skipped and the inbox still delivers.
 */
export function PlatformCredentialsPanel({ makerspaceId, enabledModules, walletOn }: {
  makerspaceId: number; enabledModules: readonly string[]; walletOn: boolean;
}) {
  const client = useQueryClient();
  const location = useLocation();
  const usage = useSpacePlanUsage(makerspaceId, true);
  const channels = useChannels(makerspaceId);
  const email = useQuery({ queryKey: ["api-settings", makerspaceId], retry: false,
    queryFn: () => staffRequest<{ email_provider_configured?: boolean; smtp_host?: string }>(`/admin/makerspace/${makerspaceId}/api-settings`),
    enabled: enabledModules.includes("email") });
  const wallet = useQuery({ queryKey: walletKeys.scope({ kind: "space", makerspaceId }), retry: false, enabled: walletOn,
    queryFn: () => walletCredentialsApi.read({ kind: "space", makerspaceId }) });
  const [confirm, setConfirm] = useState<{ key: PlatformSwitch; value: boolean } | null>(null);
  const rows = new Map((channels.data?.results ?? []).map(row => [row.channel, row]));
  const save = useMutation({
    mutationFn: async ({ key, value }: { key: PlatformSwitch; value: boolean }): Promise<unknown> => {
      if (key === "wallet") return walletCredentialsApi.save({ kind: "space", makerspaceId }, { use_platform_credentials: value });
      const spec = channelSpecs().find(item => item.key === key)!;
      // A channel with no settings row is created by this save, so it keeps today's on/off defaults.
      const row: Channel | undefined = rows.get(key as ChannelKey);
      const base = row ? {} : (({ enabled, personal_enabled }) => ({ enabled, personal_enabled }))(defaultChannel(spec));
      return staffRequest<Channel>(`/integrations/makerspace/${makerspaceId}/channels/${key}`,
        { method: "PATCH", body: JSON.stringify({ ...base, use_platform_sender: value }) });
    },
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: spacePlanKey(makerspaceId) }),
      client.invalidateQueries({ queryKey: ["notify-contract", makerspaceId] }),
      client.invalidateQueries({ queryKey: walletKeys.scope({ kind: "space", makerspaceId }) })]),
  });
  const sectionHref = (section: string) => location.pathname.replace(/\/settings(\/[^/]*)?\/?$/, `/settings/${section}`) + location.search;
  const own = (key: ChannelKey) => channels.data ? Boolean(rows.get(key)?.credentials_set) : null;
  const all: Row[] = [
    ...(enabledModules.includes("email") ? [{ key: "email" as const, label: t`Email`, usageKey: USAGE_KEY.email, section: "email",
      own: email.data ? Boolean(email.data.email_provider_configured || email.data.smtp_host) : null, ownHint: t`Set under Email sending.` }] : []),
    ...(enabledModules.includes("sms") ? [{ key: "sms" as const, label: t`Text messages`, usageKey: USAGE_KEY.sms, own: own("sms"), ownHint: t`Set in SMS below.` }] : []),
    ...(enabledModules.includes("whatsapp") ? [{ key: "whatsapp" as const, label: t`WhatsApp`, usageKey: USAGE_KEY.whatsapp, own: own("whatsapp"), ownHint: t`Set in WhatsApp below.` }] : []),
    ...(enabledModules.includes("mobile") ? [{ key: "native_push" as const, label: t`App push`, usageKey: USAGE_KEY.native_push, own: null,
      ownHint: t`Always sent through the Space Works app.` }] : []),
    ...(walletOn ? [{ key: "wallet" as const, label: t`Wallet passes`, usageKey: USAGE_KEY.wallet, section: "wallet",
      own: wallet.data ? wallet.data.effective?.apple === "space" || wallet.data.effective?.google === "space" : null, ownHint: t`Set under Wallet passes.` }] : []),
  ];
  if (!all.length) return null;
  const switches = usage.data?.platform_switches ?? {};
  const toggle = (key: PlatformSwitch, value: boolean) => (key === "sms" || key === "whatsapp") && rows.get(key)?.personal_enabled
    ? setConfirm({ key, value }) : save.mutate({ key, value });
  return <section aria-labelledby={`platform-credentials-${makerspaceId}`} className="grid gap-3 py-4">
    <div className="grid gap-1">
      <h3 id={`platform-credentials-${makerspaceId}`} className="title-section">{t`Platform credentials`}</h3>
      <p className="max-w-prose text-sm text-muted">{t`This space's own credentials always come first and are never limited. When it has none, the platform's can send for it, counted against the monthly allowance the platform operator sets. Turn that off and the channel is simply skipped; the inbox still delivers.`}</p>
    </div>
    {usage.isError ? <ErrorText resource={t`platform credential settings`} onRetry={() => { void usage.refetch(); }} /> : null}
    <ul className="grid gap-2">{all.map(row => {
      const usageRow = usage.data?.platform_resources?.find(item => item.key === row.usageKey);
      const on = switches[row.key] ?? true;
      const words = usageText(usageRow);
      return <li key={row.key} className="grid gap-2 rounded-xl border border-line bg-panel p-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
        <div className="grid min-w-0 gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink">{row.label}</p>
            {row.own === null ? null : <StatusPill label={row.own ? t`Own credentials set` : t`No own credentials`} tone={row.own ? "success" : "neutral"} />}
            {usageRow && usageRow.level !== "ok" ? <StatusPill label={usageRow.level === "limit" ? t`Platform allowance used up` : t`Platform allowance nearly used`}
              tone={usageRow.level === "limit" ? "danger" : "warn"} /> : null}
          </div>
          <p className="text-xs text-muted">{row.section ? <Link className="underline underline-offset-2" to={sectionHref(row.section)}>{row.ownHint}</Link> : row.ownHint}
            {words ? ` · ${words}` : ""}</p>
        </div>
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" role="switch" className="h-5 w-5 accent-accent" checked={on} disabled={save.isPending || !usage.data}
            onChange={event => toggle(row.key, event.target.checked)} />
          <span>{t`Use the platform's credentials when this space has none`}<span className="sr-only">: {row.label}</span></span>
        </label>
      </li>;
    })}</ul>
    {save.error ? <p role="alert" className="text-sm text-danger">{save.error.message}</p> : null}
    <ConfirmDialog open={confirm !== null} title={t`Change the sender?`} pending={save.isPending}
      message={t`Switching the platform sender for this channel reconnects it: people who connected their number for personal messages will need to connect again.`}
      confirmLabel={t`Change sender`} onCancel={() => setConfirm(null)}
      onConfirm={() => { if (confirm) save.mutate(confirm, { onSettled: () => setConfirm(null) }); }} />
  </section>;
}
