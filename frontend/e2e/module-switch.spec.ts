import { expect, test } from "@playwright/test";

import { StaffApi, staffConsole } from "./r2";

// Decision 128 C-10: a Space Manager switches a module off and on again; switching off keeps every row, the
// area disappears (console nav, API answers module_disabled) and switching back on restores it.
// Each probe is one cheap GET the module's own gate guards; `link` is the console nav entry it owns.
const MODULES: Array<{ key: string; probe: (id: number) => string; link?: string; write?: unknown }> = [
  { key: "reports", probe: (id) => `/admin/makerspace/${id}/reports/catalog`, link: "Reports" },
  { key: "events", probe: (id) => `/admin/makerspaces/${id}/events/`, link: "Events" },
  { key: "bookings", probe: (id) => `/admin/makerspaces/${id}/spaces/`, link: "Bookings" },
  { key: "machines", probe: (id) => `/admin/makerspaces/${id}/machine-access`, link: "Machines" },
  // Reading loan rules and currency stays open while the rail is off (#95); the provider write is the rail.
  { key: "payments", probe: (id) => `/admin/makerspace/${id}/payment-settings`, write: { provider: "stripe" } },
  { key: "membership", probe: (id) => `/admin/makerspaces/${id}/membership-plans` },
];

test.describe("module switch", () => {
  test.describe.configure({ mode: "serial" });
  for (const mod of MODULES) {
    test(`${mod.key}: off hides the area and refuses the API, on brings it back`, async ({ page, request }) => {
      test.setTimeout(120_000);
      const staff = await StaffApi.open(request);
      await staff.installModules(mod.key);
      const url = mod.probe(staff.makerspaceId);
      const probe = () => staff.call<{ code?: string }>(mod.write ? "PATCH" : "GET", url, mod.write, false);
      // Installed: the module gate lets the request through (it may still answer 400/403 for other reasons).
      expect((await probe()).status, `${mod.key} reachable while installed`).not.toBe(404);
      try {
        await staff.post(`/admin/makerspace/${staff.makerspaceId}/modules/uninstall`, { key: mod.key });
        const off = await probe();
        // An off switch leaves no API surface: 404 with the typed code (guards.SurfaceOff).
        expect(off.status).toBe(404);
        expect(JSON.stringify(off.body)).toContain("module_disabled");
        if (mod.link) {
          await staffConsole(page, "dashboard");
          await expect(page.getByRole("navigation").getByRole("link", { name: mod.link, exact: true })).toHaveCount(0);
        }
      } finally {
        await staff.installModules(mod.key);
      }
      expect((await probe()).status, `${mod.key} back after install`).not.toBe(404);
      if (mod.link) {
        await staffConsole(page, "dashboard");
        await expect(page.getByRole("navigation").getByRole("link", { name: mod.link, exact: true }).first()).toBeVisible();
      }
    });
  }
});

