import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { MemberUsagePanel } from "./MemberUsagePanel";
import { memberUsageKey } from "./memberUsageApi";
import { chartSpec, errorResponse, mockAnalyticsFetch, renderAnalytics } from "../../test/analyticsFixtures";
import { expectNoA11yViolations } from "../../test/axe";

afterEach(() => vi.unstubAllGlobals());
const series = { rows: [{ period: "2026-10-01", count: 2 }], chart_spec: chartSpec() };
const money = {
  paid_by_currency: { USD: "10", INR: "200" }, outstanding_by_currency: { USD: "3", INR: "25" },
  totals: { rows: [{ currency: "USD", paid_total: "10", outstanding_total: "3" }, { currency: "INR", paid_total: "200", outstanding_total: "25" }],
    chart_spec: chartSpec("currency", ["paid_total", "outstanding_total"], { currency_field: "currency", partition: "currency" }) },
};

it("renders personal loan, machine, booking, event and per-currency payment summaries", async () => {
  const fetcher = mockAnalyticsFetch(() => ({ usage_available: true,
    loans: { count: 2, returned_count: 1, currently_out: 1, monthly: series },
    machines: { hours: "4.5", monthly: series, top_machines: series }, bookings: { count: 2, monthly: series },
    events: { attended_count: 2, chart: series }, payments: money }));
  const { client, container } = renderAnalytics(<MemberUsagePanel makerspaceId={11} />);
  await screen.findByText("2 loans, 1 returned, 1 currently out.");
  expect(screen.getByText(/4.5 recorded manual machine hours/)).toBeInTheDocument();
  expect(screen.getByText("2 events attended.")).toBeInTheDocument();
  expect(screen.getByText("USD: 10 paid, 3 outstanding.")).toBeInTheDocument();
  expect(screen.getByText("INR: 200 paid, 25 outstanding.")).toBeInTheDocument();
  fireEvent.click(screen.getAllByRole("button", { name: "Show report data" })[0]);
  expect(client.getQueryData(memberUsageKey(11))).toBeDefined();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(String(fetcher.mock.calls[0][0])).toContain("/member/makerspaces/11/my-usage");
  await expectNoA11yViolations(container);
});

it("retains payments with the membership usage gate off", async () => {
  mockAnalyticsFetch(() => ({ usage_available: false, payments: money }));
  renderAnalytics(<MemberUsagePanel makerspaceId={11} />);
  await screen.findByText("USD: 10 paid, 3 outstanding.");
  expect(screen.queryByRole("heading", { name: "Loans" })).not.toBeInTheDocument();
});

it.each([403, 404])("hides the entire section for status %s", async status => {
  mockAnalyticsFetch(() => errorResponse(status));
  const { container } = renderAnalytics(<MemberUsagePanel makerspaceId={11} />);
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});

it("isolates server state when switching makerspaces", async () => {
  mockAnalyticsFetch(url => ({ usage_available: true, events: { attended_count: url.pathname.includes("/11/") ? 2 : 8, chart: series } }));
  const { rerender, client } = renderAnalytics(<MemberUsagePanel makerspaceId={11} />);
  await screen.findByText("2 events attended.");
  // The same provider owns both tenant keys; changing the endpoint cannot reuse another space's rows.
  const { QueryClientProvider } = await import("@tanstack/react-query");
  rerender(<QueryClientProvider client={client}><MemberUsagePanel makerspaceId={12} /></QueryClientProvider>);
  await screen.findByText("8 events attended.");
  expect(screen.queryByText("2 events attended.")).not.toBeInTheDocument();
  expect(client.getQueryData(memberUsageKey(11))).toBeDefined();
  expect(client.getQueryData(memberUsageKey(12))).toBeDefined();
});

it("reports a service failure and offers retry", async () => {
  mockAnalyticsFetch(() => errorResponse(503));
  renderAnalytics(<MemberUsagePanel makerspaceId={11} />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load your usage");
  expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
});
