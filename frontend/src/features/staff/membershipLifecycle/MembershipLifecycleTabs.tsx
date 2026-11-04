import { useState } from "react";

import { featureEnabled } from "../../../lib/features";
import { MemberImportWizard } from "../memberImport/MemberImportWizard";
import { ErasureQueue } from "./ErasureQueue";
import { InviteLinksManager } from "./InviteLinksManager";
import { MemberRegisterList } from "./MemberRegisterList";
import { MembershipInsights } from "./MembershipInsights";
import { MonthlySummaryToggle } from "./MonthlySummaryToggle";
import { RenewalDesk } from "./RenewalDesk";
import { TitlesManager } from "./TitlesManager";

type Tab = { key: string; label: string; href: string };
const has = (features: string[], key: string) => featureEnabled(features, `membership.${key}`);

/** The release-2 membership tabs, each shown only while its switch is on (#95: off = no UI). */
export function lifecycleTabs(features: string[], membershipEnabled: boolean): Tab[] {
  if (!membershipEnabled) return [];
  const tabs: [string, string, boolean][] = [
    ["register", "Register", has(features, "register_tools")],
    ["renewals", "Renewals", has(features, "renewal_desk")],
    ["insights", "Insights", has(features, "insights")],
    ["import", "Import", has(features, "import")],
    ["tools", "Titles and links", has(features, "titles") || has(features, "admission_tools")
      || has(features, "erasure") || has(features, "monthly_summary")],
  ];
  return tabs.filter(([, , on]) => on).map(([key, label]) => ({ key, label, href: `#${key}` }));
}

export function MembershipLifecycleTab({ tab, makerspaceId, slug, features, canManageMakerspace, standing }: {
  tab: string; makerspaceId: number; slug: string; features: string[]; canManageMakerspace: boolean; standing: string;
}) {
  const [importing, setImporting] = useState(false);
  if (tab === "register") return <MemberRegisterList makerspaceId={makerspaceId} initialStanding={standing} />;
  if (tab === "renewals") return <RenewalDesk makerspaceId={makerspaceId} />;
  if (tab === "insights") return <MembershipInsights makerspaceId={makerspaceId} />;
  if (tab === "import") return <section aria-label="Member import" className="grid gap-3">
    <p className="text-sm text-muted">Bring members over from a spreadsheet. Each person is invited by email and joins when they accept; nobody is linked to an existing account for them.</p>
    <div><button className="desk-button-primary" type="button" onClick={() => setImporting(true)}>Import members</button></div>
    <MemberImportWizard makerspaceId={makerspaceId} open={importing} onClose={() => setImporting(false)}
      sheetsEnabled={has(features, "import_sheets")} />
  </section>;
  if (tab === "tools") return <div className="grid gap-4">
    {has(features, "titles") ? <TitlesManager makerspaceId={makerspaceId} /> : null}
    {has(features, "admission_tools") ? <InviteLinksManager makerspaceId={makerspaceId} slug={slug} /> : null}
    {has(features, "erasure") ? <ErasureQueue makerspaceId={makerspaceId} /> : null}
    {has(features, "monthly_summary") ? <MonthlySummaryToggle makerspaceId={makerspaceId} canManageMakerspace={canManageMakerspace} /> : null}
  </div>;
  return null;
}
