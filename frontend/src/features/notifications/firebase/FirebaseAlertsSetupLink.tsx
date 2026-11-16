import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../../lib/api";

export function FirebaseAlertsSetupLink({ makerspaceId, member = false }: { makerspaceId: number; member?: boolean }) {
  const config = useQuery({ queryKey: ["firebase-browser-config", member ? "member" : "staff", makerspaceId], queryFn: () => (member ? memberRequest : staffRequest)<{ configured: boolean }>(`/notifications/browser-firebase/${makerspaceId}/config`), retry: false });
  if (!config.data?.configured) return null;
  return <a className="desk-button" href={`/firebase-alerts/setup?space=${makerspaceId}`}>{t`Set up Firebase browser notifications`}</a>;
}

