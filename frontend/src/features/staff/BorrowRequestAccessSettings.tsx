import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";

// Read-only (owner decision #80): who may ask follows from the modules, so there is nothing to
// set here -- only to explain. Without Member accounts, borrowers ask with no account.
type Settings = { request_access: "members" | "accounts" | "contact" };
const LABELS: Record<Settings["request_access"], string> = {
  members: t`Active members only`,
  accounts: t`Anyone with a signed-in account`,
  contact: t`Anyone, with name, phone and a confirmed email (no account)`,
};

export function BorrowRequestAccessSettings({ makerspaceId }: { makerspaceId: number }) {
  const query = useQuery({
    queryKey: ["makerspace-settings", makerspaceId],
    queryFn: () => staffRequest<Settings>(`/admin/makerspaces/${makerspaceId}`),
  });
  const label = query.data ? LABELS[query.data.request_access] : "";
  return <SettingsRow label={t`Borrow request access`} helper="Staff review every request. With Member accounts on, borrowers sign in (with Membership, only active members); without it, accounts are staff-only and borrowers give name, phone and an email confirmed by a code. A superadmin changes these areas in Modules.">
    {query.error ? <p role="alert" className="text-sm text-danger">{query.error.message}</p> : <p className="text-sm text-ink">{query.data ? label : t`Loading...`}</p>}
  </SettingsRow>;
}
