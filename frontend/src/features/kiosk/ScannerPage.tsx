import { t } from "@lingui/core/macro";
import { useMutation } from "@tanstack/react-query";
import { KioskLayout } from "../../components/layouts";
import { Card, EmptyState, KeyValueCard, ScanWorkbench, StatusPill } from "../../components/ui";
import { ThemeToggle } from "../../components/ThemeToggle";
import { staffRequest } from "../../lib/api";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { useStationConnection } from "./useStationConnection";

type ResolveResult = { target: Record<string, string | number>; allowed_actions: string[] };
const words = (value: string) => value.replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());

export function ScannerPage() {
  const online = useStationConnection();
  const context = currentSessionContext();
  const resolve = useMutation({ mutationFn: (payload: string) => {
    return staffRequest<ResolveResult>("/admin/qr/resolve", {
      method: "POST", body: JSON.stringify({ payload: payload.trim() }),
    }, context);
  } });
  const target = resolve.data?.target;
  const title = target ? String(target.name ?? target.label ?? target.product ?? "Label resolved") : "Scan a label";
  return <KioskLayout context={{ title: t`Scanner`, subtitle: t`Scan a label or paste its code.` }} connection={{ online }}
    mode="work" headerActions={[]} state={{ status: "ready" }}
    work={{ capture: <ScanWorkbench searchLabel="QR payload" helper="Scan or paste QR payload. Only labels your staff role in this makerspace can see are resolved."
      onFind={payload => resolve.mutate(payload)} onScan={payload => resolve.mutate(payload)} findPending={resolve.isPending}
      result={resolve.isError ? { tone: "danger", title: t`Couldn't resolve this label`, summary: resolve.error.message,
        next: { label: t`Try again`, onClick: () => { if (resolve.variables) resolve.mutate(resolve.variables); } } } : target ? {
          tone: "success", title, summary: t`${words(String(target.type ?? "Item"))} · Label resolved`,
          next: { label: t`Next scan`, onClick: () => resolve.reset() },
        } : undefined} />,
      panel: <div className="grid gap-5">{target ? <>
        <KeyValueCard title={t`Resolved label`} items={Object.entries(target).filter(([key]) => key !== "type").map(([key, value]) => ({ label: words(key), value: key === "status" ? <StatusPill label={words(String(value))} tone={value === "issued" || value === "out" ? "accent" : value === "available" ? "success" : "neutral"} /> : String(value) }))} />
        <Card><h2 className="title-panel">{t`Available actions`}</h2><p className="mt-2 text-sm text-muted">{t`Your account is allowed to perform these actions in the staff console.`}</p>
          <div className="mt-4 flex flex-wrap gap-2">{resolve.data?.allowed_actions.map(action => <StatusPill key={action} label={words(action)} tone="neutral" />)}</div>
          {!resolve.data?.allowed_actions.length ? <p className="mt-3 text-sm text-muted">{t`No actions are available for this label.`}</p> : null}
        </Card>
      </> : <EmptyState message={t`Scan a label or paste its code. Its details will appear here.`} />}
      <ThemeToggle /></div> }} />;
}
