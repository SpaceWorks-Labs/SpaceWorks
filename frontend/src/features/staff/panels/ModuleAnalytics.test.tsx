import { setRouteSessionContext } from "../../../lib/api/sessionContext";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { ModuleAnalytics } from "./ModuleAnalytics";
import { mockAnalyticsFetch, renderAnalytics, reportData, reportItem, space } from "../../../test/analyticsFixtures";

afterEach(() => vi.unstubAllGlobals());
it.each([
  ["inventory", "inventory-utilisation"], ["machines", "machine-usage"], ["bookings", "booking-occupancy"],
  ["events", "event-funnel"], ["members", "membership-growth"], ["payments", "payments-ageing"],
  ["notifications", "communications-health"], ["communications", "communications-health"], ["devices", "device-health"],
])("embeds the catalog-authorized %s console report", async (tab, key) => {
  mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? { results: [reportItem(key), reportItem("unrelated")] } : reportData());
  renderAnalytics(<ModuleAnalytics makerspace={space} tab={tab} />);
  const link = await screen.findByRole("link", { name: "Open in reports" });
  expect(link).toHaveAttribute("href", `/m/workshop/admin/reports?report=${key}`);
  expect(screen.queryByRole("option", { name: "unrelated" })).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole("button", { name: "Show report data" }));
  expect(screen.getByRole("table")).toHaveTextContent("7");
});

it("does not fetch analytics when reports or the source module is off", () => {
  const fetcher = mockAnalyticsFetch(() => ({}));
  const { container } = renderAnalytics(<ModuleAnalytics makerspace={{ ...space, enabled_modules: ["reports"] }} tab="machines" />);
  expect(container).toBeEmptyDOMElement();
  expect(fetcher).not.toHaveBeenCalled();
});

it("does not fetch analytics from a handover-only notification console", () => {
  const fetcher = mockAnalyticsFetch(() => ({}));
  const { container } = renderAnalytics(<ModuleAnalytics makerspace={space} tab="notifications" guestOnly />);
  expect(container).toBeEmptyDOMElement();
  expect(fetcher).not.toHaveBeenCalled();
});

it("keeps core money analytics available with the online payment rail disabled", async () => {
  mockAnalyticsFetch(url => url.pathname.endsWith("catalog") ? { results: [reportItem("payments-ageing")] } : reportData());
  renderAnalytics(<ModuleAnalytics makerspace={{ ...space, enabled_modules: ["reports"] }} tab="payments" />);
  expect(await screen.findByRole("link", { name: "Open in reports" })).toBeInTheDocument();
});

beforeEach(() => setRouteSessionContext("person"));
afterEach(() => setRouteSessionContext("person"));
