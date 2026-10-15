import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { Callout, ErrorText } from "../../components/ui";
import type { Makerspace } from "./panels/shared";
import { TenantMigrationDisclosure } from "./TenantMigrationDisclosure";
import { TenantMigrationExports } from "./TenantMigrationExports";
import { TenantMigrationImports } from "./TenantMigrationImports";
import { TenantMigrationPairings } from "./TenantMigrationPairings";
import { getDisclosureClosure, listPairings, tenantMigrationKeys } from "./tenantMigrationApi";
import { adminQueryState } from "./adminPresentation";

const stages = [
  { key: "disclosure", label: "Review disclosure", summary: "Source · approve the exact identity closure" },
  { key: "pairings", label: "Pin deployments", summary: "Both · compare fingerprints out of band" },
  { key: "export", label: "Encrypt export", summary: "Source · encrypt for the target recipient" },
  { key: "import", label: "Import & resolve", summary: "Target · resolve every identity" },
  { key: "verify", label: "Verify & materialise", summary: "Target · review the persisted report" },
  { key: "cutover", label: "Cut over", summary: "Both · signed, one-way cutover" },
];
export function TenantMigrationPanel({ makerspace }: { makerspace: Makerspace }) {
  const [step, setStep] = useState(0);
  const closure = useQuery({ queryKey: tenantMigrationKeys.closure(makerspace.id), queryFn: () => getDisclosureClosure(makerspace.id) });
  const pairings = useQuery({ queryKey: tenantMigrationKeys.pairings, queryFn: listPairings });
  return <FlowLayout title="Tenant migration" subject={makerspace.name} standalone={false}
    state={pairings.data ? { status: "ready" } : adminQueryState(pairings, "deployment pairings")} current={stages[step].key}
    steps={stages.map((stage, index) => ({ ...stage, state: index === step ? "current" : "todo" }))}
    work={<div className="grid gap-6">
      <Callout size="panel" tone="danger" lead="This is one-way." body="Cut-over archives the source space; it isn't deleted, and archives sit outside the purge guarantee." />
      {pairings.isError && pairings.data ? <ErrorText resource="deployment pairings" onRetry={() => { void pairings.refetch(); }} /> : null}
      {closure.isError ? <ErrorText resource="disclosure closure" onRetry={() => { void closure.refetch(); }} /> : null}
      <TenantMigrationDisclosure makerspaceId={makerspace.id} active={step === 0} />
      <TenantMigrationPairings pairings={pairings.data ?? []} active={step === 1} />
      <TenantMigrationExports makerspaceId={makerspace.id} tenantName={makerspace.name} closureDigest={closure.data?.digest}
        pairings={pairings.data ?? []} active={step === 2 || step === 5} phase={step === 5 ? "cutover" : "export"} />
      <TenantMigrationImports pairings={pairings.data ?? []} active={step >= 3} phase={step === 3 ? "import" : step === 4 ? "verify" : "cutover"} />
    </div>}
    footer={{ back: step > 0 ? { label: "Previous step", onClick: () => setStep(step - 1) } : undefined,
      next: { label: step === stages.length - 1 ? "Review disclosure again" : `Continue to ${stages[step + 1].label.toLowerCase()}`, onClick: () => setStep((step + 1) % stages.length) } }}
    onCancel={() => window.history.back()} leaveGuard="Your saved migration records stay on the server. Unsaved fields will be lost if you leave this task." />;
}
