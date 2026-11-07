import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, Skeleton, StatusPill } from "../../../../components/ui";
import type { Identity } from "../../../../components/ui/types";
import type { Machine, MachineType, MachineStatus } from "../../machinesApi";

type Props = {
  machineTypes: MachineType[];
  machines: Machine[];
  machinesLoading: boolean;
  machinesFailed: boolean;
  typesLoading: boolean;
  typesFailed: boolean;
  hrefFor: (machineType: MachineType) => string;
};

// Only the states worth surfacing on a card. `idle` is the resting state and says nothing;
// `reserved` is normal scheduling. What an operator scans this grid for is "what is busy"
// and "what is not usable".
const HIGHLIGHT: { status: MachineStatus; label: string; tone: "success" | "warn" | "danger" }[] = [
  { status: "running", label: "running", tone: "success" },
  { status: "maintenance", label: t`in maintenance`, tone: "warn" },
  { status: "offline", label: "offline", tone: "danger" },
];

/** The type's own configured icon (short text the space chose) when set, else the generic cog. */
export function machineTypeIdentity(machineType: MachineType): Identity {
  const icon = machineType.icon?.trim();
  return icon ? { kind: "code", code: icon } : { kind: "icon", icon: "Cog", tone: "accent" };
}

/** The machines index: one card per reachable machine type.
 *
 * The card grid is built from the SERVER-SCOPED type list merged with the types nested in
 * the machines response -- never from effective action strings. A `MANAGE_MACHINES` grant
 * is scoped per ROLE through link tables, no links means no machines, and a membership with
 * a null `assigned_role` is EXEMPT: none of that is expressible client-side, and four
 * previous phases have shipped a bug by trying.
 */
export function MachineTypeCards({
  machineTypes,
  machines,
  machinesLoading,
  machinesFailed,
  typesLoading,
  typesFailed,
  hrefFor,
}: Props) {
  if (typesLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label={t`Loading machine types`}>
        {[0, 1, 2].map((slot) => (
          <Skeleton key={slot} className="h-28 w-full" />
        ))}
      </div>
    );
  }

  // An empty grid is only honest after a SUCCESSFUL load -- the same rule the per-type
  // machine list follows. A failed request that renders "no machine types" tells an
  // operator their console is empty when it is merely broken.
  if (!typesFailed && !machineTypes.length) {
    return (
      <EmptyState message={t`No machine types available. Ask your space manager to configure your machine access.`} />
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {machineTypes.map((machineType) => {
        const owned = machines.filter((machine) => machine.machine_type.id === machineType.id);
        const highlights = HIGHLIGHT.map(({ status, label, tone }) => ({
          label,
          tone,
          count: owned.filter((machine) => machine.status === status).length,
        })).filter((entry) => entry.count > 0);

        return (
          <ListRow
            key={machineType.id}
            href={hrefFor(machineType)} title={machineType.name}
            identity={machineTypeIdentity(machineType)}
            meta={<span className="flex flex-wrap items-center gap-2">
              {/* A count is stated as fact, so it must not be stated while the fleet is
                  still loading or after the request failed. */}
              {machinesLoading ? (
                <span className="tabular-nums text-xs text-muted">{t`counting…`}</span>
              ) : machinesFailed ? (
                <span className="tabular-nums text-xs text-muted">{t`count unavailable`}</span>
              ) : (
                <span className="chip">{owned.length} {owned.length === 1 ? "machine" : "machines"}</span>
              )}
              {!machinesLoading && !machinesFailed
                ? highlights.map((entry) => (
                    <StatusPill key={entry.label} label={`${entry.count} ${entry.label}`} tone={entry.tone} />
                  ))
                : null}
            </span>}
          />
        );
      })}
    </div>
  );
}
