import { t } from "@lingui/core/macro";
import type { StaffAuthUser } from "../../../lib/api";
import type { Makerspace } from "../panels/shared";
import { Users } from "../StaffTabLoaders";
import { AccountsSection } from "../platformParity/AccountsSection";
import { PlatformSectionPage } from "./PlatformSectionPage";
import { PlatformAdminsSection } from "./PlatformDefaultsSections";

type Props = { makerspaces: Makerspace[]; currentUser: StaffAuthUser; onAuthRefresh: () => void };

/** People & access: any account on the platform, and each space's staff, where only the superadmin grants Space Manager. */
export function PlatformAccessPage({ makerspaces, currentUser, onAuthRefresh }: Props) {
  return <PlatformSectionPage title={t`People & access`}
    subtitle={t`Find any account, disable it or reset its two-step sign-in, and manage each space's staff and Space Managers.`}
    sections={[
      { key: "accounts", label: t`Accounts`, rows: <AccountsSection />,
        description: t`Search by username or email. Disabling ends every session and revokes staff roles; a reset clears every sign-in factor.` },
      { key: "staff", label: t`Staff & Space Managers`,
        page: <Users makerspaces={makerspaces} isSuperadmin currentUser={currentUser} onAuthRefresh={onAuthRefresh} /> },
      { key: "admins", label: t`Platform admins`, rows: <PlatformAdminsSection />,
        description: t`Accounts that run the whole platform. Contact details stay hidden; opening this list is recorded.` },
    ]} />;
}
