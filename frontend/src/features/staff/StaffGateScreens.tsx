import { t } from "@lingui/core/macro";
import { Fingerprint, Smartphone } from "lucide-react";
import { CenteredCardLayout } from "../../components/layouts";
import { MfaReadinessBanner } from "../../components/shell/MfaReadinessBanner";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EnrolPasskeyInPlace } from "../auth/passkeys/EnrolPasskeyInPlace";
import { passkeysSupported } from "../auth/passkeys/webauthn";

/** Where the console sends someone to set up two-step sign-in, and back again afterwards. */
export function enrolmentHref() {
  const back = window.location.pathname + window.location.search;
  return `/mfa?${new URLSearchParams({ return: back })}`;
}

/** Signed in, but this account holds no staff role or delegated grant anywhere. */
export function NoStaffRoleScreen({ memberHref, onSignOut }: { memberHref: string; onSignOut: () => void }) {
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "Lock", tone: "warn" }}
    eyebrow={t`Staff console`} title={t`You don't have a staff role yet`}
    body={t`Staff roles are given to people's own accounts. Ask a Space Manager to add you, or accept the staff invitation they emailed you.`}
    primary={{ label: t`Go to your member area`, href: memberHref }} escape={{ label: t`Sign out`, onClick: onSignOut }}
    footer={<ThemeToggle />} />;
}

const FACTORS = [
  { Glyph: Fingerprint, title: t`A passkey`, body: t`Your fingerprint, face or device PIN. Nothing to type.` },
  { Glyph: Smartphone, title: t`An authenticator app`, body: t`A 6-digit code from an app on your phone.` },
];

/** #128 C-1, after the 3-day grace: staff screens wait for two-step sign-in; member features never do. */
export function MfaEnrollmentScreen({ memberHref, onSignOut }: { memberHref: string; onSignOut: () => void }) {
  return <CenteredCardLayout state={{ status: "ready" }} media={{ icon: "ShieldCheck", tone: "accent" }}
    eyebrow={t`Staff console`} title={t`Set up two-step sign-in`}
    body={t`Staff screens need a second step at sign-in. Add a passkey here now, or set up an authenticator app; you'll come straight back. Your member area keeps working meanwhile.`}
    content={<div className="grid gap-4"><ul className="grid gap-3" aria-label={t`Ways to add a second step`}>
      {FACTORS.map(({ Glyph, title, body }) => <li key={title} className="flex items-start gap-3 rounded-xl border border-line bg-surface p-4">
        <Glyph aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-accent-ink" />
        <span className="grid gap-1"><span className="font-semibold text-ink">{title}</span><span className="text-sm text-muted">{body}</span></span>
      </li>)}
    </ul>{passkeysSupported() ? <EnrolPasskeyInPlace /> : null}</div>}
    primary={{ label: t`Set up two-step sign-in`, href: enrolmentHref() }}
    escape={{ label: t`Go to your member area`, href: memberHref }}
    footer={<div className="flex flex-wrap items-center justify-between gap-3"><button type="button" className="desk-button-ghost min-h-11" onClick={onSignOut}>{t`Sign out`}</button><ThemeToggle /></div>} />;
}

/** The banner shown at each sign-in during the grace (the shell's readiness banner). */
export function MfaGraceBanner({ endsAt }: { endsAt: string }) {
  return <div className="mb-4"><MfaReadinessBanner endsAt={endsAt} href={enrolmentHref()} /></div>;
}
