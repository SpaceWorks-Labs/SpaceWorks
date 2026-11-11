import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Callout, ErrorText, SegmentedControl } from "../../../components/ui";
import { TenantMigrationImports } from "../TenantMigrationImports";
import { TenantMigrationPairings } from "../TenantMigrationPairings";
import { listPairings, tenantMigrationKeys } from "../tenantMigrationApi";

type Step = "pairings" | "import" | "verify" | "cutover";

/**
 * Data & recovery › Import a space (0.12.0 row 22). The TARGET half of a tenant migration:
 * pin the source deployment, upload its encrypted archive, resolve identities, verify, then
 * activate. None of it belongs to an existing space (pairings and imports are platform-wide
 * routes), so the superadmin reaches it without choosing one. The SOURCE half (disclosure,
 * export, quiesce) stays on the space's own Tenant migration page.
 */
export function TenantImportSection() {
  const [step, setStep] = useState<Step>("import");
  const pairings = useQuery({ queryKey: tenantMigrationKeys.pairings, queryFn: listPairings });
  const steps = [
    { value: "pairings", label: t`Link the two servers` },
    { value: "import", label: t`Import & resolve` },
    { value: "verify", label: t`Verify & materialise` },
    { value: "cutover", label: t`Switch over` },
  ];
  return <div className="@container grid min-w-0 gap-5 py-5">
    <p className="text-sm text-muted">{t`Bring a space in from another server. The old server exports an encrypted archive for this server; the imported space stays in “importing” until you activate it with the old server's signed switch-over receipt.`}</p>
    <Callout size="inline" tone="warn" lead={t`Activation is one-way.`} body={t`The source space is archived once this target goes live.`} />
    <SegmentedControl label={t`Import step`} value={step} options={steps} onChange={value => setStep(value as Step)} />
    {pairings.isError ? <ErrorText resource={t`deployment pairings`} onRetry={() => { void pairings.refetch(); }} /> : null}
    <TenantMigrationPairings pairings={pairings.data ?? []} active={step === "pairings"} />
    {step !== "pairings" ? <TenantMigrationImports pairings={pairings.data ?? []} phase={step} /> : null}
  </div>;
}
