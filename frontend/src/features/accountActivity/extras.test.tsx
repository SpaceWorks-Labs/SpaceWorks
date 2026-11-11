import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { memberRequest, staffRequest, StructuredApiError } from "../../lib/api";
import { SecurityActivityPage } from "./SecurityActivityPage";
import { OrganizationLeaveCard } from "../organizationLeave/OrganizationLeaveCard";
import { PlatformInsightsPage } from "../platformInsights/PlatformInsightsPage";
import { SeriesGuestList } from "../staff/eventProgramme/SeriesGuestList";
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), memberRequest: vi.fn(), staffRequest: vi.fn() }));
function mount(element: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })) { return render(<MemoryRouter><QueryClientProvider client={client}>{element}</QueryClientProvider></MemoryRouter>); }
beforeEach(() => { vi.mocked(memberRequest).mockReset(); vi.mocked(staffRequest).mockReset(); });
it("shows only own allowlisted activity projection", async () => {
  vi.mocked(memberRequest).mockResolvedValue({ count: 1, results: [{ id: 1, action: "auth.password_changed", created_at: "2026-10-18T10:00:00Z" }] });
  mount(<SecurityActivityPage />); expect(await screen.findByText("auth password changed")).toBeVisible(); expect(memberRequest).toHaveBeenCalledWith("/member/security-activity/?page=1");
});
it("requires leave acknowledgement and retains sole-owner refusal", async () => {
  vi.mocked(memberRequest).mockRejectedValue(new Error("The last active owner cannot leave.")); mount(<OrganizationLeaveCard organizationId={3} name="Maker group" version={4} />);
  expect(screen.getByRole("button", { name: "Leave organization" })).toBeDisabled(); fireEvent.click(screen.getByRole("checkbox")); fireEvent.click(screen.getByRole("button", { name: "Leave organization" })); expect(await screen.findByRole("alert")).toHaveTextContent("last active owner");
});
it("uses platform context and displays only aggregate metrics", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ window: { starts_at: "2026-09-18", ends_at: "2026-10-18" }, growth: [], staff_mfa: { active: 10, enabled: 8, without_mfa: 2, adoption_percent: 80 }, outbox: [] });
  mount(<PlatformInsightsPage />); expect(await screen.findByText("80%")).toBeVisible(); expect(staffRequest).toHaveBeenCalledWith("/admin/platform/insights/", {}, "platform");
});
it("scopes series guest filters to the series and renders missing data safely", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ count: 1, results: [{ member_id: 5, registration_id: null, occurrences: [{ event_id: 42, registration_id: 71, status: "registered", attended_at: null }] }], next: null, previous: null });
  mount(<SeriesGuestList seriesId={8} />); expect(await screen.findByText("Guest 1")).toBeVisible(); fireEvent.change(screen.getByLabelText("Registration status"), { target: { value: "registered" } }); await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/event-series/8/guests/?page=1&status=registered")); expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
it("removes cached series guests after a permission-refused refresh", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  vi.mocked(staffRequest).mockResolvedValue({ count: 1, results: [{ member_id: 5, registration_id: null, occurrences: [{ event_id: 42, registration_id: 71, name: "Private guest", status: "registered", attended_at: null }] }] });
  mount(<SeriesGuestList seriesId={8} />, client); expect(await screen.findByText("Private guest")).toBeVisible();
  vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(404, { detail: "Not found" })); await client.invalidateQueries({ queryKey: ["event-series-guests", 8] });
  expect(await screen.findByRole("alert")).toHaveTextContent("no longer available"); expect(screen.queryByText("Private guest")).not.toBeInTheDocument(); await waitFor(() => expect(client.getQueryCache().find({ queryKey: ["event-series-guests", 8] })?.state.data).toBeUndefined());
});
