import { t } from "@lingui/core/macro";
import { Skeleton } from "../../../components/ui";
import { toast } from "../../../components/ui/toastStore";
import { actionErrorText } from "./ActionDialog";
import { useSetSpaceHostingType, useSpaceHostingType, type HostingType } from "./limitsApi";

export const hostingTypeLabels = (): Record<HostingType, string> => ({ own: t`Own space`, hosted: t`Hosted space` });
const help = (): Record<HostingType, string> => ({
  own: t`Your own space: no plan, no limits, no hosting bills. Everything is unlimited.`,
  hosted: t`A space you host for someone else: its plan, limits, trial and hosting bills apply.`,
});

/** Decision 236: the superadmin marks a space as their own or as hosted. Off while hosting is off. */
export function HostingTypeControl({ makerspaceId }: { makerspaceId: number }) {
  const state = useSpaceHostingType(makerspaceId);
  const save = useSetSpaceHostingType(makerspaceId);
  if (state.isLoading) return <Skeleton className="h-16 w-full" />;
  if (state.isError || !state.data) return null; // not reachable here: the drawer simply omits it
  const { hosting_type: current, hosting_active: active } = state.data;
  const disabled = !active || save.isPending;
  return <fieldset className="grid gap-2" aria-describedby={active ? undefined : "hosting-type-off"}>
    <legend className="title-panel mb-1">{t`Hosting type`}</legend>
    {(["own", "hosted"] as const).map(value => <label key={value} className="flex min-h-11 items-start gap-3 text-sm text-ink">
      <input type="radio" name={`hosting-type-${makerspaceId}`} className="mt-1" value={value} checked={current === value} disabled={disabled}
        onChange={() => save.mutate(value, { onSuccess: () => toast(t`Hosting type saved.`) })} />
      <span className="grid"><span className="font-semibold">{hostingTypeLabels()[value]}</span><span className="text-muted">{help()[value]}</span></span>
    </label>)}
    {active ? null : <p id="hosting-type-off" className="text-sm text-muted">{t`Turn on "Host other makerspaces" in Platform settings to choose. While it is off, every space is treated as your own.`}</p>}
    {save.error ? <p role="alert" className="text-sm text-danger">{actionErrorText(save.error)}</p> : null}
  </fieldset>;
}
