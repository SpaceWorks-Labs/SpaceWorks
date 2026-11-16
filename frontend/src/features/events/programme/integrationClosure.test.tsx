import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProgrammeWebsiteSections } from "../ProgrammeWebsiteSections";
import { runtimeTenantConfig } from "../../../lib/runtimeConfig";
it("turns runtime delight flags on unless explicitly turned off", () => {
  window.__TENANT__ = {}; expect(runtimeTenantConfig().uiDelightEnabled).toBe(true);
  window.__TENANT__ = { uiDelightEnabled: true, uiEasterEggsEnabled: false };
  expect(runtimeTenantConfig()).toMatchObject({ uiDelightEnabled: true, uiEasterEggsEnabled: false });
  delete window.__TENANT__;
});
it("public sections accept approved profile paths and omit arbitrary URLs", () => {
  render(<ProgrammeWebsiteSections rows={[{ kind: "judges", layout: "grid", items: [{ display_name: "Alex", profile_url: "https://foreign.test/" }, { display_name: "Kim", profile_url: "/kim" }] }]} />);
  expect(screen.getByText("Alex")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View public profile" })).toHaveAttribute("href", "/kim");
});
