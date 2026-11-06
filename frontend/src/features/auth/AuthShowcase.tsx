import { t } from "@lingui/core/macro";
import { ListRow, StatusPill } from "../../components/ui";

/** Static product examples belong to AuthLayout's inert decorative showcase slot. */
export function AuthShowcase() {
  return <>
    <div className="-rotate-3"><ListRow title={t`Multimeter`} identity={{ kind: "icon", icon: "Wrench", tone: "accent" }} meta="Due back Fri" /></div>
    <div className="translate-x-3 rotate-2"><ListRow title={t`Request #1042`} identity={{ kind: "icon", icon: "Settings", tone: "info" }} right={<StatusPill label={t`Ready for handover`} tone="success" />} /></div>
    <div className="-rotate-2 justify-self-start"><StatusPill label={t`Return photo attached`} tone="success" /></div>
  </>;
}
