import { t } from "@lingui/core/macro";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { Callout, KeyValueCard } from "../../components/ui";
import { type Makerspace } from "./StaffPanels";
type ApiSettingsSummary = {
  public_code: string;
  cors_allowed_origins: string[];
};

export function ApiClientsAccessSummary({
  makerspace,
  isSuperadmin,
  settings,
  loading, error, onRetry,
}: {
  makerspace: Makerspace;
  isSuperadmin: boolean;
  settings?: ApiSettingsSummary;
  loading?: boolean; error?: Error | null; onRetry?: () => void;
}) {
  return <QueryContent state={{ status: loading ? "loading" : error ? "error" : "ready", error: "Couldn't load API settings. Try again.", onRetry }}><div className="grid gap-4">
    <Callout size="card" tone="warn" lead="Keep keys in a secret manager." body="Never put them in browser code or URLs." />
    <KeyValueCard title={t`Makerspace API access`} items={[
      { label: t`Makerspace code`, value: settings?.public_code ?? makerspace.public_code },
      { label: t`Allowed browser origins`, value: isSuperadmin ? (settings?.cors_allowed_origins ?? []).join(", ") || "No active client origins" : "Managed by superadmin" },
    ]} />
  </div></QueryContent>;
}
