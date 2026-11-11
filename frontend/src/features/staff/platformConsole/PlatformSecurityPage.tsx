import { t } from "@lingui/core/macro";
import { EmptyState, ListRow } from "../../../components/ui";
import type { Makerspace } from "../panels/shared";
import { AuditLog } from "../panels/AuditLog";
import { IpAccessSection } from "../platformParity/IpAccessSection";
import { openSpaceTab } from "./openSpaceTab";
import { PlatformSectionPage } from "./PlatformSectionPage";

/** Each space's sign-in rules live on that space's Security page; the platform lock is set there (a floor it can only tighten). */
function SpaceLocks({ makerspaces }: { makerspaces: Makerspace[] }) {
  if (!makerspaces.length) return <EmptyState message={t`No spaces yet. Create one under Spaces.`} />;
  return <div className="grid gap-3">
    <p className="text-sm text-muted">{t`Open a space's Security page to change or lock its session length, CAPTCHA, passkeys and staff IP allow-list. Two-step sign-in is always on for every space staff role.`}</p>
    {makerspaces.map(space => <ListRow key={space.id} title={space.name} meta={space.public_code || space.slug}
      right={<button type="button" className="desk-button" onClick={() => openSpaceTab(space.id, "/admin/security")}>
        {t`Security settings`}<span className="sr-only"> {space.name}</span></button>} />)}
  </div>;
}

/** Platform security: deployment-wide IP rules and sign-in blocks, per-space locks, and the cross-space audit search. */
export function PlatformSecurityPage({ makerspaces }: { makerspaces: Makerspace[] }) {
  return <PlatformSectionPage title={t`Platform security`} subtitle={t`IP rules and sign-in blocks, security locks for each space, and the audit log.`}
    sections={[
      { key: "ip-access", label: t`IP access`, rows: <IpAccessSection />,
        description: t`Allow or block network addresses across the whole platform.` },
      { key: "space-locks", label: t`Space security locks`, rows: <SpaceLocks makerspaces={makerspaces} />,
        description: t`Set a minimum security level a space cannot loosen.` },
      { key: "audit", label: t`Audit log`, rows: <AuditLog platform />,
        description: t`Actions across every space. Search by action or actor, filter by space, or keep platform-level rows only.` },
    ]} />;
}
