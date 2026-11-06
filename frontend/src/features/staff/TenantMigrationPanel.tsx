import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { FlowLayout } from "../../components/layouts";
import { Callout, ErrorText } from "../../components/ui";
import type { Makerspace } from "./panels/shared";
import { TenantMigrationDisclosure } from "./TenantMigrationDisclosure";
import { TenantMigrationExports } from "./TenantMigrationExports";
import { TenantMigrationImports } from "./TenantMigrationImports";
import { TenantMigrationPairings } from "./TenantMigrationPairings";
import {
  getDisclosureClosure, listDisclosureApprovals, listImports, listMigrationExports, listPairings, tenantMigrationKeys,
  type ClosureApproval, type ImportJob, type MigrationExportJob, type Pairing,
} from "./tenantMigrationApi";

const stages = [
  { key: "disclosure", label: t`Review disclosure`, summary: t`Source · approve the exact identity closure` },
  { key: "pairings", label: t`Pin deployments`, summary: t`Both · compare fingerprints out of band` },
  { key: "export", label: t`Encrypt export`, summary: t`Source · encrypt for the target recipient` },
  { key: "import", label: t`Import & resolve`, summary: t`Target · resolve every identity` },
  { key: "verify", label: t`Verify & materialise`, summary: t`Target · review the persisted report` },
  { key: "cutover", label: t`Cut over`, summary: t`Both · signed, one-way cutover` },
];

/** The furthest stage the server records say this deployment has reached. */
function reachedStage({ approvals, closureDigest, pairings, exports, imports }: {
  approvals: ClosureApproval[]; closureDigest?: string; pairings: Pairing[]; exports: MigrationExportJob[]; imports: ImportJob[];
}) {
  if (imports.some(job => job.status === "completed")) return 5;
  if (imports.some(job => job.status === "ready")) return 4;
  if (imports.length) return 3;
  // A source deployment never holds imports: once its archive exists, cutover is what is left.
  if (exports.some(job => job.status === "available")) return 5;
  if (exports.length) return 2;
  if (pairings.length) return 2;
  // An approval of an older closure is void, so it does not count as a reviewed disclosure.
  if (approvals.some(item => !item.revoked_at && item.closure_digest === closureDigest)) return 1;
  return 0;
}

export function TenantMigrationPanel({ makerspace }: { makerspace: Makerspace }) {
  const [step, setStep] = useState<number | null>(null);
  const [visited, setVisited] = useState(0);
  const closure = useQuery({ queryKey: tenantMigrationKeys.closure(makerspace.id), queryFn: () => getDisclosureClosure(makerspace.id) });
  const pairings = useQuery({ queryKey: tenantMigrationKeys.pairings, queryFn: listPairings });
  // Same keys as the stage components, so these share their cache rather than refetching.
  const approvals = useQuery({ queryKey: tenantMigrationKeys.approvals(makerspace.id), queryFn: () => listDisclosureApprovals(makerspace.id) });
  const exports = useQuery({ queryKey: tenantMigrationKeys.exports(makerspace.id), queryFn: () => listMigrationExports(makerspace.id) });
  const imports = useQuery({ queryKey: tenantMigrationKeys.imports, queryFn: listImports });
  const settled = !closure.isLoading && !pairings.isLoading && !approvals.isLoading && !exports.isLoading && !imports.isLoading;
  const reached = reachedStage({ approvals: approvals.data ?? [], closureDigest: closure.data?.digest, pairings: pairings.data ?? [],
    exports: exports.data ?? [], imports: imports.data ?? [] });
  // Resume once, where the records say the migration stands; later progress never moves the operator.
  useEffect(() => { if (settled && step === null) { setStep(reached); setVisited(reached); } }, [settled, step, reached]);
  const current = step ?? 0;
  const furthest = Math.max(visited, reached);
  const go = (next: number) => { setStep(next); setVisited(value => Math.max(value, next)); };
  return <FlowLayout title={t`Tenant migration`} subject={makerspace.name} standalone={false}
    state={step === null ? { status: "loading" } : { status: "ready" }} current={stages[current].key}
    steps={stages.map((stage, index) => ({ ...stage, state: index === current ? "current" : index <= furthest ? "done" : "todo" }))}
    onStepSelect={key => go(stages.findIndex(stage => stage.key === key))}
    work={<div className="@container grid gap-6">
      <Callout size="panel" tone="danger" lead="This is one-way." body={t`Cut-over archives the source space; it isn't deleted, and archives sit outside the purge guarantee.`} />
      {/* A failed list stays inline: the other stages keep working without it. */}
      {pairings.isError ? <ErrorText resource="deployment pairings" onRetry={() => { void pairings.refetch(); }} /> : null}
      {closure.isError ? <ErrorText resource="disclosure closure" onRetry={() => { void closure.refetch(); }} /> : null}
      <TenantMigrationDisclosure makerspaceId={makerspace.id} active={current === 0} />
      <TenantMigrationPairings pairings={pairings.data ?? []} active={current === 1} />
      <TenantMigrationExports makerspaceId={makerspace.id} tenantName={makerspace.name} closureDigest={closure.data?.digest}
        pairings={pairings.data ?? []} active={current === 2 || current === 5} phase={current === 5 ? "cutover" : "export"} />
      <TenantMigrationImports pairings={pairings.data ?? []} active={current >= 3} phase={current === 3 ? "import" : current === 4 ? "verify" : "cutover"} />
    </div>}
    footer={{ back: current > 0 ? { label: t`Previous step`, onClick: () => go(current - 1) } : undefined,
      next: { label: current === stages.length - 1 ? t`Review disclosure again` : t`Continue to ${stages[current + 1].label.toLowerCase()}`, onClick: () => go((current + 1) % stages.length) } }}
    onCancel={() => window.history.back()} leaveGuard="Your saved migration records stay on the server. Unsaved fields will be lost if you leave this task." />;
}
