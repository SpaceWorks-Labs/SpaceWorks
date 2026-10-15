import { CenteredCardLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";

export function StaffAccessDenied({ makerspaceName, onSignOut }: { makerspaceName?: string; onSignOut: () => void }) {
  const space = makerspaceName ?? "this makerspace";
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "CircleAlert", tone: "warn" }}
    eyebrow="Access denied" title={`You do not have access to ${space}`}
    body={`This console is only for ${space}'s team. Sign in with an account that's a member here.`}
    primary={{ label: "Sign out", onClick: onSignOut }} footer={<ThemeToggle />} />;
}
