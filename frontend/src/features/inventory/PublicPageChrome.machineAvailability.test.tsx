import { expect, it, vi } from "vitest";
import type { TenantBootstrap } from "../../lib/api";
import { publicPageChrome } from "./PublicPageChrome";

vi.mock("../../lib/publicHome", () => ({ publicFamilies: () => [] }));

it("does not offer a legacy print or job link when job requests are off", () => {
  const bootstrap = { makerspace: { slug: "lab", name: "Lab" }, modules: ["machine_service", "membership", "presence", "printing"], features: [], branding: {} } as unknown as TenantBootstrap;
  const nav = publicPageChrome("lab", "Lab", path => `/m/lab/${path ?? ""}`, bootstrap).nav;
  expect(nav.some(item => /machine-jobs\/new|\/print$/.test(item.href))).toBe(false);
  const on = publicPageChrome("lab", "Lab", path => `/m/lab/${path ?? ""}`, { ...bootstrap, features: ["machines.job_requests"] }).nav;
  expect(on.some(item => item.href.endsWith("machine-jobs/new"))).toBe(true);
});
