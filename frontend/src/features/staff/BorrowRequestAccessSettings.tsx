import { useQuery } from "@tanstack/react-query";
import { SettingsRow } from "../../components/ui";
import { staffRequest } from "../../lib/api";

// Read-only: every borrow request needs a signed-in account. Which accounts follows from the
// Membership module, so there is nothing to set here -- only to explain.
type Settings = { request_access: "members" | "accounts" };

export function BorrowRequestAccessSettings({ makerspaceId }: { makerspaceId: number }) {
  const query = useQuery({
    queryKey: ["makerspace-settings", makerspaceId],
    queryFn: () => staffRequest<Settings>(`/admin/makerspaces/${makerspaceId}`),
  });
  const label = query.data?.request_access === "members" ? "Active members only" : "Anyone with a signed-in account";
  return <SettingsRow label="Borrow request access" helper="Every borrow request needs a signed-in account, and staff review each one. With Membership on, only active members can submit; a superadmin can change that area in Modules.">
    {query.error ? <p role="alert" className="text-sm text-danger">{query.error.message}</p> : <p className="text-sm text-ink">{query.data ? label : "Loading..."}</p>}
  </SettingsRow>;
}
