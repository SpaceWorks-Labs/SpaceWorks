import { QueryClient } from "@tanstack/react-query";
import { expect, it } from "vitest";
import { filterTabsByEnabledModules } from "../features/staff/staffTabs";
import { capabilityOn } from "./features";

// area_frontend_shell: source switch changes must not destroy cached tenant data.
it.each(["reports", "analytics"])("%s disappears and restores without reading the other tenant cache", (module) => {
  const client = new QueryClient();
  const home = ["makerspace", 7] as const;
  const away = ["makerspace", 8] as const;
  const original = { enabled_modules: [module], enabled_features: [], name: "ورشة 🔧" };
  const foreign = { enabled_modules: [], enabled_features: [], name: "Private other tenant" };
  client.setQueryData(home, original);
  client.setQueryData(away, foreign);
  const visible = () => filterTabsByEnabledModules([module, "email-logs", "members"], client.getQueryData<typeof original>(home));
  expect(visible()).toEqual([module, "email-logs", "members"]);
  client.setQueryData(home, { ...original, enabled_modules: [] });
  expect(visible()).toEqual(["email-logs", "members"]);
  expect(client.getQueryData(away)).toEqual(foreign);
  client.setQueryData(home, original);
  expect(visible()).toEqual([module, "email-logs", "members"]);
  expect(client.getQueryData(home)).toEqual(original);
  client.clear();
});

it.each(["notifications.member_inbox", "notifications.member_preferences", "notifications.quiet_hours", "notifications.digests"])(
  "%s remains stored while its parent is off and becomes effective on restoration", (feature) => {
    const original = { enabled_modules: ["notifications"], enabled_features: [feature] };
    expect(capabilityOn(original, feature)).toBe(true);
    const disabled = { ...original, enabled_modules: [] };
    expect(capabilityOn(disabled, feature)).toBe(false);
    expect(disabled.enabled_features).toEqual([feature]);
    expect(capabilityOn({ ...disabled, enabled_modules: ["notifications"] }, feature)).toBe(true);
    expect(capabilityOn({ ...original, enabled_features: [] }, feature)).toBe(false);
  });

it("removing the online rail retains finance and audit history navigation", () => {
  const tabs = ["finance", "email-logs", "audit"];
  const enabled = { enabled_modules: ["payments"], enabled_features: ["finance.ledger"] };
  expect(filterTabsByEnabledModules(tabs, enabled)).toEqual(tabs);
  expect(filterTabsByEnabledModules(tabs, { ...enabled, enabled_modules: [] })).toEqual(tabs);
});
