import type { TenantBootstrap } from "../../lib/api";

/** Public configuration only; the server still checks this person's membership and presence. */
export function machineIntakeAvailable(bootstrap: TenantBootstrap | null | undefined, slug: string): boolean {
  return !!bootstrap && bootstrap.makerspace?.slug === slug && ["machine_service", "membership", "presence"].every(key => bootstrap.modules?.includes(key)) && bootstrap.features?.includes("machines.job_requests") === true;
}
