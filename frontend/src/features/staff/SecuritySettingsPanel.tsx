import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SettingsLayout } from "../../components/layouts";
import { ErrorText, SettingsRow } from "../../components/ui";
import {
  getSecuritySettings, lockSecuritySetting, securitySettingsKey, unlockSecuritySetting, updateSecuritySettings,
  type SecuritySettings,
} from "../../lib/api/securitySettings";
import { adminQueryState } from "./adminPresentation";
import { PiiAccessBanner } from "./PiiAccessBanner";
import { SecurityRow } from "./security/SecurityRow";
import { KeyEventsHistory } from "./security/KeyEventsHistory";
import type { Makerspace } from "./panels/shared";
import { useRoutedSubTab } from "./useRoutedSubTab";

/**
 * Per-space security settings. The Space Manager and a platform superadmin change them;
 * a superadmin can also lock one so the space cannot loosen it. Every change asks for a
 * fresh identity check (the API client prompts for it) and lands in the audit log.
 *
 * Open item C16: each section is its own routed page (`/admin/security/pii`), like Settings,
 * so a long single page becomes three short ones that can be linked to directly.
 */
export function SecuritySettingsPanel({ makerspace }: { makerspace: Makerspace }) {
  const queryClient = useQueryClient();
  const key = securitySettingsKey(makerspace.id);
  const query = useQuery({ queryKey: key, queryFn: () => getSecuritySettings(makerspace.id) });
  const settle = (data: SecuritySettings) => queryClient.setQueryData(key, data);
  const update = useMutation({ mutationFn: ({ setting, value }: { setting: string; value: unknown }) =>
    updateSecuritySettings(makerspace.id, { [setting]: value }), onSuccess: settle });
  const lock = useMutation({ mutationFn: ({ setting, floor, note }: { setting: string; floor: unknown; note: string }) =>
    lockSecuritySetting(makerspace.id, setting, floor, note), onSuccess: settle });
  const unlock = useMutation({ mutationFn: (setting: string) => unlockSecuritySetting(makerspace.id, setting),
    onSuccess: settle });
  const data = query.data;
  const pending = update.isPending || lock.isPending || unlock.isPending;
  const error = update.error ?? lock.error ?? unlock.error;
  const route = useRoutedSubTab();

  const sections = [
    { id: "sign-in", title: t`Sign-in requirements`,
      description: data?.can_lock ? t`You can lock a setting so this space cannot loosen it: a switch is held at its stricter value, any other setting at its current value or stricter. Only a platform superadmin removes a lock.`
        : t`A setting locked by the platform cannot be loosened here.`,
      rows: data ? <>
        <SettingsRow label={t`Staff MFA`} helper={t`Every staff role needs two-step sign-in (an authenticator app or a passkey). New staff get three days to set it up; member features never need it.`}>
          <p className="text-sm text-ink">{t`Required for every space staff role (platform rule)`}</p>
        </SettingsRow>
        {data.settings.map(setting => <SecurityRow key={setting.key} setting={setting} data={data} pending={pending}
          onChange={value => update.mutate({ setting: setting.key, value })}
          onLock={(floor, note) => lock.mutate({ setting: setting.key, floor, note })}
          onUnlock={() => unlock.mutate(setting.key)} />)}
        {error ? <ErrorText message={error.message} /> : null}
      </> : null },
    { id: "pii", title: t`Platform access to personal data`,
      description: t`Platform administrators see members' personal details masked unless they open a short, recorded window.`,
      rows: <PiiAccessBanner makerspaceId={makerspace.id} /> },
    { id: "key-history", title: t`Encryption key history`,
      description: t`Rotations and re-keys of this space's data keys. They are started by the platform team; nothing secret is shown.`,
      rows: <KeyEventsHistory makerspaceId={makerspace.id} /> },
  ];
  const active = sections.find(section => section.id === route.segment) ?? sections[0];
  return <SettingsLayout
    header={{ title: t`Security`, subtitle: t`Sign-in rules for staff at ${makerspace.name}. Changes need a fresh identity check and are recorded in the audit log.` }}
    tabs={sections.map(section => ({ key: section.id, label: section.title, href: route.href(section.id) }))}
    activeTab={active.id} state={adminQueryState(query, "security settings")} sections={[active]} />;
}
