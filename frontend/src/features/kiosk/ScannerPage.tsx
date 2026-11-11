import { t } from "@lingui/core/macro";
import { assetStatusLabel } from "../staff/panels/InventoryPanelShared";
import { useMutation } from "@tanstack/react-query";
import { KioskLayout } from "../../components/layouts";
import { Card, EmptyState, KeyValueCard, ScanWorkbench, StatusPill } from "../../components/ui";
import { ThemeToggle } from "../../components/ThemeToggle";
import { staffRequest } from "../../lib/api";
import { currentSessionContext } from "../../lib/api/sessionContext";
import { useStationConnection } from "./useStationConnection";

type ResolveResult = { target: Record<string, string | number>; allowed_actions: string[] };
const words = (value: string) => value.replace(/_/g, " ").replace(/^./, letter => letter.toUpperCase());
const targetTypeLabel = (type: string) => type === "box" ? t`Box` : type === "asset" ? t`Asset` : type === "product" ? t`Item` : type === "member_card" ? t`Member card` : words(type);
const actionLabel = (action: string) => ({ view: t`View`, record_scan: t`Record scan`, return: t`Return`, checkout: t`Check out`,
  direct_handout: t`Direct handout`, contents: t`Contents`, move_container: t`Move container`, revoke: t`Revoke` } as Record<string, string>)[action] ?? words(action);
const fieldLabel = (key: string) => ({ id: t`ID`, name: t`Name`, label: t`Label`, code: t`Code`, asset_tag: t`Asset tag`,
  product: t`Item`, status: t`Status` } as Record<string, string>)[key] ?? words(key);

export function ScannerPage() {
  const online = useStationConnection();
  const context = currentSessionContext();
  const resolve = useMutation({ mutationFn: (payload: string) => {
    return staffRequest<ResolveResult>("/admin/qr/resolve", {
      method: "POST", body: JSON.stringify({ payload: payload.trim() }),
    }, context);
  } });
  const target = resolve.data?.target;
  const title = target ? String(target.name ?? target.label ?? target.product ?? t`Label resolved`) : t`Scan a label`;
  return <KioskLayout context={{ title: t`Scanner`, subtitle: t`Scan a label or paste its code.` }} connection={{ online }}
    mode="work" headerActions={[]} state={{ status: "ready" }}
    work={{ capture: <ScanWorkbench searchLabel={t`QR payload`} helper={t`Scan or paste QR payload. Only labels your staff role in this makerspace can see are resolved.`}
      onFind={payload => resolve.mutate(payload)} onScan={payload => resolve.mutate(payload)} findPending={resolve.isPending}
      result={resolve.isError ? { tone: "danger", title: t`Couldn't resolve this label`, summary: resolve.error.message,
        next: { label: t`Try again`, onClick: () => { if (resolve.variables) resolve.mutate(resolve.variables); } } } : target ? {
          tone: "success", title, summary: t`${targetTypeLabel(String(target.type ?? "product"))} · Label resolved`,
          next: { label: t`Next scan`, onClick: () => resolve.reset() },
        } : undefined} />,
      panel: <div className="grid gap-5">{target ? <>
        <KeyValueCard title={t`Resolved label`} items={Object.entries(target).filter(([key]) => key !== "type").map(([key, value]) => ({ label: fieldLabel(key), value: key === "status" ? <StatusPill label={assetStatusLabel(String(value))} tone={value === "issued" || value === "out" ? "accent" : value === "available" ? "success" : "neutral"} /> : String(value) }))} />
        <Card><h2 className="title-panel">{t`Available actions`}</h2><p className="mt-2 text-sm text-muted">{t`Your account is allowed to perform these actions in the staff console.`}</p>
          <div className="mt-4 flex flex-wrap gap-2">{resolve.data?.allowed_actions.map(action => <StatusPill key={action} label={actionLabel(action)} tone="neutral" />)}</div>
          {!resolve.data?.allowed_actions.length ? <p className="mt-3 text-sm text-muted">{t`No actions are available for this label.`}</p> : null}
        </Card>
      </> : <EmptyState message={t`Scan a label or paste its code. Its details will appear here.`} />}
      <ThemeToggle /></div> }} />;
}
