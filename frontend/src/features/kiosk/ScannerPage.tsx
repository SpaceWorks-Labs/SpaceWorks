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
    if (!context.startsWith("staff:")) throw new Error("Open the scanner for your makerspace from its staff console.");
    return staffRequest<ResolveResult>("/admin/qr/resolve", {
      method: "POST", body: JSON.stringify({ payload: payload.trim() }),
    }, context);
  } });
  const target = resolve.data?.target;
  const title = target ? String(target.name ?? target.label ?? target.product ?? "Label resolved") : "Scan a label";
  return <KioskLayout context={{ title: "Scanner", subtitle: "Scan a label or paste its code." }} connection={{ online }}
    mode="work" headerActions={[]} state={{ status: "ready" }}
    work={{ capture: <ScanWorkbench searchLabel="QR payload" helper="Scan or paste QR payload. Only labels available to your staff account can be resolved."
      onFind={payload => resolve.mutate(payload)} onScan={payload => resolve.mutate(payload)} findPending={resolve.isPending}
      result={resolve.isError ? { tone: "danger", title: "Couldn't resolve this label", summary: resolve.error.message,
        next: { label: "Try again", onClick: () => { if (resolve.variables) resolve.mutate(resolve.variables); } } } : target ? {
          tone: "success", title, summary: `${words(String(target.type ?? "Item"))} · Label resolved`,
          next: { label: "Next scan", onClick: () => resolve.reset() },
        } : undefined} />,
      panel: <div className="grid gap-5">{target ? <>
        <KeyValueCard title="Resolved label" items={Object.entries(target).filter(([key]) => key !== "type").map(([key, value]) => ({ label: words(key), value: key === "status" ? <StatusPill label={words(String(value))} tone={value === "issued" || value === "out" ? "accent" : value === "available" ? "success" : "neutral"} /> : String(value) }))} />
        <Card><h2 className="title-panel">Available actions</h2><p className="mt-2 text-sm text-muted">Your account is allowed to perform these actions in the staff console.</p>
          <div className="mt-4 flex flex-wrap gap-2">{resolve.data?.allowed_actions.map(action => <StatusPill key={action} label={words(action)} tone="neutral" />)}</div>
          {!resolve.data?.allowed_actions.length ? <p className="mt-3 text-sm text-muted">No actions are available for this label.</p> : null}
        </Card>
      </> : <EmptyState message="Scan a label or paste its code. Its details will appear here." />}
      <ThemeToggle /></div> }} />;
}
