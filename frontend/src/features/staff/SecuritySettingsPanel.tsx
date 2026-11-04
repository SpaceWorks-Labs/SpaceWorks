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
import type { Makerspace } from "./panels/shared";

/**
 * Per-space security settings. The Space Manager and a platform superadmin change them;
 * a superadmin can also lock one so the space cannot loosen it. Every change asks for a
 * fresh identity check (the API client prompts for it) and lands in the audit log.
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

  return <SettingsLayout
    header={{ title: "Security", subtitle: `Sign-in rules for staff at ${makerspace.name}. Changes need a fresh identity check and are recorded in the audit log.` }}
    state={adminQueryState(query, "security settings")}
    sections={[
      { id: "sign-in", title: "Sign-in requirements",
        description: data?.can_lock ? "You can lock a setting so this space cannot loosen it: a switch is held at its stricter value, any other setting at its current value or stricter. Only a platform superadmin removes a lock."
          : "A setting locked by the platform cannot be loosened here.",
        rows: data ? <>
          <SettingsRow label="Staff MFA" helper="Every staff role needs two-step sign-in (an authenticator app or a passkey). New staff get three days to set it up; member features never need it.">
            <p className="text-sm text-ink">Required for every staff role (platform rule)</p>
          </SettingsRow>
          {data.settings.map(setting => <SecurityRow key={setting.key} setting={setting} data={data} pending={pending}
            onChange={value => update.mutate({ setting: setting.key, value })}
            onLock={(floor, note) => lock.mutate({ setting: setting.key, floor, note })}
            onUnlock={() => unlock.mutate(setting.key)} />)}
          {error ? <ErrorText message={error.message} /> : null}
        </> : null },
      { id: "pii", title: "Platform access to personal data",
        description: "Platform administrators see members' personal details masked unless they open a short, recorded window.",
        rows: <PiiAccessBanner makerspaceId={makerspace.id} /> },
    ]} />;
}
