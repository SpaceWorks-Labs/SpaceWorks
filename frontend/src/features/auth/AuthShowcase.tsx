import { ListRow, StatusPill } from "../../components/ui";

/** Static product examples belong to AuthLayout's inert decorative showcase slot. */
export function AuthShowcase() {
  return <>
    <div className="-rotate-3"><ListRow title="Multimeter" identity={{ kind: "icon", icon: "Wrench", tone: "accent" }} meta="Due back Fri" /></div>
    <div className="translate-x-3 rotate-2"><ListRow title="Request #1042" identity={{ kind: "icon", icon: "Settings", tone: "info" }} right={<StatusPill label="Ready for handover" tone="success" />} /></div>
    <div className="-rotate-2 justify-self-start"><StatusPill label="Return photo attached" tone="success" /></div>
  </>;
}
