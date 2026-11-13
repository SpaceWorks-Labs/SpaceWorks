import { t } from "@lingui/core/macro";
import { CenteredCardLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";

export function StaffAccessDenied({ makerspaceName, onSignOut }: { makerspaceName?: string; onSignOut: () => void }) {
  const space = makerspaceName ?? "this makerspace";
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Lock", tone: "warn" }}
    eyebrow={t`Access denied`} title={t`You do not have access to ${space}`}
    body={t`This console is only for ${space}'s team. Sign in with an account that's a member here.`}
    primary={{ label: t`Sign out`, onClick: onSignOut }} footer={<ThemeToggle />} />;
}
