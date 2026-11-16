import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { Link } from "react-router-dom";
import { UserMenu } from "../../components/shell/UserMenu";
import { logout, memberRequest } from "../../lib/api";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { onSessionCleared } from "../../lib/api/sessionContext";

/** Identity is server verified; this menu grants no tenant authority. */
export function HubAccount() {
  const owner = useSyncExternalStore(onSessionCleared, () => getSessionOwner("person"), () => "");
  const client = useQueryClient();
  const account = useQuery({ queryKey: ["hub-account", owner],
    queryFn: () => memberRequest<{ id: number; display_name?: string; username?: string }>("/auth/me"), retry: false });
  if (!owner || !account.data || String(account.data.id) !== owner || account.isError) return <Link to="/member" className="desk-button whitespace-nowrap">{t`Sign in`}</Link>;
  return <UserMenu above={false} compact user={{ name: account.data.display_name || account.data.username || t`Account`,
    menu: [{ label: t`My account`, href: "/member" }, { label: t`Account & two-step sign-in`, href: "/mfa" }],
    onSignOut: () => { void logout("person").catch(() => undefined).finally(() => { client.removeQueries({ queryKey: ["hub-account"] }); }); } }} />;
}
