import { t } from "@lingui/core/macro";

import { useOpsTabs } from "../opsPresentation";
import { NeedsFixShelf } from "./NeedsFixShelf";
import { ProblemReportsQueue } from "./ProblemReportsQueue";
import type { Makerspace } from "./shared";

/**
 * The inventory area's repair desk: the broken-returns shelf and the open problem reports.
 * Both need EDIT_INVENTORY (the tab's own gate); the problem-report list, like its triage route,
 * is served only while the reports module is on, so the sub-tab disappears with it.
 */
export function NeedsFixTab({ makerspace }: { makerspace: Makerspace }) {
  const reportsOn = makerspace.enabled_modules === undefined || makerspace.enabled_modules.includes("reports");
  const tabs = useOpsTabs("section", [{ key: "shelf", label: t`Repair shelf` },
    ...(reportsOn ? [{ key: "problems", label: t`Problem reports` }] : [])], "shelf");
  const nav = reportsOn ? { tabs: tabs.tabs, activeTab: tabs.active } : {};
  return <div onClickCapture={tabs.onClickCapture}>
    {tabs.active === "problems" ? <ProblemReportsQueue makerspace={makerspace} nav={nav} /> : <NeedsFixShelf makerspace={makerspace} nav={nav} />}
  </div>;
}
