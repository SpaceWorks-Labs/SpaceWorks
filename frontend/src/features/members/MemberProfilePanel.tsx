import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";
import { GlobalProfileEditor } from "../profile/edit/GlobalProfileEditor";

/**
 * The member's own profile. It is one global, account-level profile (not per makerspace), so this panel is only a
 * frame: it renders the same editor as /member/profile and links to the standalone page.
 */
export function MemberProfilePanel() {
  return <div className="grid gap-5">
    <p className="text-sm text-muted">{t`Your profile is one page for your whole account, shown across every space you belong to. `}
      <RouteLink href="/member/profile" className="font-semibold text-accent-ink underline-offset-2 hover:underline">{t`Open the full profile editor`}</RouteLink></p>
    <GlobalProfileEditor />
  </div>;
}
