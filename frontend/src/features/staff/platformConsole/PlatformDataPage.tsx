import { t } from "@lingui/core/macro";
import { BackupRestorePanel } from "../StaffTabLoaders";
import { RestoreDrillsSection } from "../platformParity/RestoreDrillsSection";
import { SelfhostMovesSection } from "../platformParity/SelfhostMovesSection";
import { OffsiteDestinationsSection } from "./offsite/OffsiteDestinationsSection";
import { TenantImportSection } from "./TenantImportSection";
import { PlatformSectionPage, type PlatformSection } from "./PlatformSectionPage";

/**
 * Data & recovery: backups and restores (whole platform or one space), offsite copies, restore
 * drills and self-host moves. Every destructive step keeps its own typed confirmation and the
 * server's fresh sign-in check; key rotation and whole-platform recovery stay on the server.
 */
export function PlatformDataPage({ unavailableApps = [] }: { unavailableApps?: readonly string[] }) {
  const sections: PlatformSection[] = [
    // No space id: the scope picker chooses the platform or a space.
    { key: "backups", label: t`Backup & restore`, page: <BackupRestorePanel isSuperadmin />,
      description: t`Back up the whole platform or one space, and restore from a backup.` },
    { key: "offsite", label: t`Offsite copies`, rows: <OffsiteDestinationsSection />,
      description: t`Send a second copy of every backup to storage somewhere else.` },
    { key: "restore-drills", label: t`Restore drills`, rows: <RestoreDrillsSection />,
      description: t`Practise a restore on a schedule so you know your backups work.` },
    // A deployment that does not ship tenant migration has no self-host move or import routes at all.
    ...(unavailableApps.includes("tenant_migration") ? [] : [{ key: "selfhost-moves", label: t`Self-host moves`, rows: <SelfhostMovesSection />,
        description: t`Requests from spaces that want to move to their own server.` },
      // Row 22: importing a space needs no chosen space (it creates one).
      { key: "space-import", label: t`Import a space`, rows: <TenantImportSection />,
        description: t`Bring a space in from another server.` }]),
  ];
  return <PlatformSectionPage title={t`Data & recovery`}
    subtitle={t`Backups, restores, offsite copies, restore drills, moves between servers and space imports.`} sections={sections} />;
}
