import { expect, it } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { machineIntakeAvailable } from "./machineIntakeAvailability";

it("requires loaded matching-space service, membership and presence without claiming personal eligibility", () => {
  const bootstrap = { makerspace: { slug: "lab" }, modules: ["machine_service", "membership", "presence"], features: ["machines.job_requests"] } as TenantBootstrap;
  expect(machineIntakeAvailable(bootstrap, "lab")).toBe(true);
  expect(machineIntakeAvailable(bootstrap, "other")).toBe(false);
  expect(machineIntakeAvailable(undefined, "lab")).toBe(false);
  for (const missing of bootstrap.modules) expect(machineIntakeAvailable({ ...bootstrap, modules: bootstrap.modules.filter(key => key !== missing) }, "lab")).toBe(false);
  expect(machineIntakeAvailable({ ...bootstrap, features: [] }, "lab")).toBe(false);
});
