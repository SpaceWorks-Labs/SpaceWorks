import type { StaffAuthUser } from "../../lib/api";
import type { Makerspace } from "./panels/shared";
import { TenantUsagePanel } from "./StaffTabLoaders";
import { Users, EmailTemplatesPanel, EmailLogPanel, ApiClientsPanel, PlatformSettingsPanel, MakerspaceSettingsPanel, ModulesPanel, DataExportsPanel, BackupRestorePanel, TenantMigrationPanel, SecuritySettingsPanel, PiiAccessBanner } from "./StaffTabLoaders";

export function StaffPlatformTabContent({ activeTab, activeMakerspace, makerspaces, isSuperadmin, canManageMakerspace, currentUser, onAuthRefresh, allowedTabs, singleTenantLocked }: { activeTab: string; activeMakerspace: Makerspace; makerspaces: Makerspace[]; isSuperadmin: boolean; canManageMakerspace: boolean; currentUser: StaffAuthUser; onAuthRefresh: () => void; allowedTabs?: readonly string[]; singleTenantLocked?: boolean }) {
  const makerspaceKey = activeMakerspace.id;
  return <>
      {activeTab === "usage" && canManageMakerspace ? <TenantUsagePanel key={makerspaceKey} makerspace={activeMakerspace} /> : null}
      {activeTab === "api" ? (
        <ApiClientsPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          isSuperadmin={isSuperadmin}
          canManageMakerspace={canManageMakerspace}
        />
      ) : null}
      {activeTab === "settings" ? (
        <MakerspaceSettingsPanel
          key={makerspaceKey}
          makerspace={activeMakerspace}
          isSuperadmin={isSuperadmin}
          canManageMakerspace={canManageMakerspace}
          allowedTabs={allowedTabs}
          singleTenantLocked={singleTenantLocked}
        />
      ) : null}
      {activeTab === "security" && canManageMakerspace ? (
        <SecuritySettingsPanel key={makerspaceKey} makerspace={activeMakerspace} />
      ) : null}
      {/* Staff names and emails sit on Users; a superadmin sees them masked until a window opens. */}
      {activeTab === "users" && isSuperadmin ? <PiiAccessBanner key={`pii:${makerspaceKey}`} makerspaceId={makerspaceKey} compact /> : null}
      {activeTab === "emailtemplates" ? (
        <EmailTemplatesPanel key={makerspaceKey} makerspace={activeMakerspace} />
      ) : null}
      {activeTab === "email-logs" && canManageMakerspace ? (
        <EmailLogPanel key={makerspaceKey} makerspace={activeMakerspace} />
      ) : null}
      {activeTab === "modules" && isSuperadmin ? (
        <ModulesPanel key={makerspaceKey} makerspaceId={activeMakerspace.id} />
      ) : null}
      {activeTab === "platform" ? (
        <PlatformSettingsPanel platformHosting={Boolean(activeMakerspace.platform_hosting)} />
      ) : null}
      {activeTab === "users" && canManageMakerspace ? (
        <Users makerspaces={makerspaces} isSuperadmin={isSuperadmin} currentUser={currentUser} onAuthRefresh={onAuthRefresh} />
      ) : null}
      {activeTab === "exports" && canManageMakerspace ? (
        <DataExportsPanel key={makerspaceKey} makerspaceId={makerspaceKey} />
      ) : null}
      {activeTab === "backups" && canManageMakerspace ? (
        <BackupRestorePanel key={makerspaceKey} makerspaceId={makerspaceKey} isSuperadmin={isSuperadmin} />
      ) : null}
      {activeTab === "migration" && isSuperadmin ? (
        <TenantMigrationPanel key={makerspaceKey} makerspace={activeMakerspace} />
      ) : null}
  </>;
}
