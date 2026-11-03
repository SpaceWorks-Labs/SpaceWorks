import { CenteredCardLayout } from "../../components/layouts";
import { Callout } from "../../components/ui";
import { ThemeToggle } from "../../components/ThemeToggle";

/** Where the console sends someone to set up two-step sign-in, and back again afterwards. */
export function enrolmentHref() {
  const back = window.location.pathname + window.location.search;
  return `/mfa?${new URLSearchParams({ return: back })}`;
}

/** Signed in, but this account holds no staff role or delegated grant anywhere. */
export function NoStaffRoleScreen({ memberHref, onSignOut }: { memberHref: string; onSignOut: () => void }) {
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Lock", tone: "warn" }}
    eyebrow="Staff console" title="You don't have a staff role yet"
    body="Staff roles are given to people's own accounts. Ask a Space Manager to add you, or accept the staff invitation they emailed you."
    primary={{ label: "Go to your member area", href: memberHref }} escape={{ label: "Sign out", onClick: onSignOut }}
    footer={<ThemeToggle />} />;
}

/** #128 C-1, after the 3-day grace: staff screens wait for two-step sign-in; member features never do. */
export function MfaEnrollmentScreen({ memberHref, onSignOut }: { memberHref: string; onSignOut: () => void }) {
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldCheck", tone: "accent" }}
    eyebrow="Staff console" title="Set up two-step sign-in"
    body="Staff screens need an authenticator or passkey on your account. It takes a minute; you'll come straight back here. Your member area keeps working meanwhile."
    primary={{ label: "Set up two-step sign-in", href: enrolmentHref() }}
    escape={{ label: "Go to your member area", href: memberHref }}
    footer={<div className="flex flex-wrap items-center justify-between gap-3"><button type="button" className="desk-button-ghost min-h-11" onClick={onSignOut}>Sign out</button><ThemeToggle /></div>} />;
}

/** The banner shown at each sign-in during the grace (S-D may restyle it; the contract stays). */
export function MfaGraceBanner({ endsAt }: { endsAt: string }) {
  const date = new Date(endsAt).toLocaleString(undefined, { weekday: "long", day: "numeric", month: "long", hour: "numeric", minute: "2-digit" });
  return <div className="mb-4"><Callout size="banner" tone="warn" lead="Set up two-step sign-in"
    body={`Staff screens need it from ${date}. Member features are not affected.`}
    action={{ label: "Set it up now", href: enrolmentHref() }} /></div>;
}
