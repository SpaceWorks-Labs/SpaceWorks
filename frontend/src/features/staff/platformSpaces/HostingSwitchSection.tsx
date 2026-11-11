import { t } from "@lingui/core/macro";
import { ErrorText, Skeleton, StatusPill } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { useHostingSwitch, useSetHostingSwitch } from "./limitsApi";

export const HOSTING_DOCS_URL = "https://github.com/SpaceWorks-Labs/SpaceWorks/blob/main/docs/self-hosting.md#plans-and-hosting-other-makerspaces-optional";

/** The one on/off switch for plans, limits, hosting requests and the platform fallbacks (default off). */
export function HostingSwitchSection() {
  const state = useHostingSwitch();
  const save = useSetHostingSwitch();
  if (state.isLoading) return <Skeleton className="h-16 w-full" />;
  if (state.isError || !state.data) return <ErrorText resource={t`the hosting switch`} onRetry={() => { void state.refetch(); }} />;
  const { enabled, forced_by_environment: forced } = state.data;
  return <div className="grid gap-3">
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
      <input type="checkbox" checked={Boolean(enabled)} disabled={forced || save.isPending}
        onChange={event => save.mutate(event.target.checked, { onSuccess: () => toast(t`Hosting switch saved.`) })} />
      {t`Host other makerspaces on this install`}
      <StatusPill label={enabled ? t`On` : t`Off`} tone={enabled ? "success" : "neutral"} />
    </label>
    <p className="text-sm text-muted">{t`Lets this install host other makerspaces: plans and limits per space, host-your-makerspace requests, subdomains and shared credentials. Off by default; nothing changes for your own spaces while it's off.`}</p>
    {forced ? <p className="text-sm text-muted">{t`Set by the server (MANAGED_PLANS_ENABLED). Remove that setting to control it here.`}</p> : null}
    <a className="desk-link inline-flex min-h-11 w-fit items-center" href={HOSTING_DOCS_URL} target="_blank" rel="noreferrer">{t`How hosting other makerspaces works ↗`}</a>
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
  </div>;
}
