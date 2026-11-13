import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { BroadcastDeliveryControls } from "./BroadcastDeliveryControls";
import { BroadcastComposer } from "./BroadcastComposer";
import type { BroadcastCampaign } from "./broadcastApi";
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../../lib/api")>(), staffRequest: vi.fn() }));
const campaign: BroadcastCampaign = { id: 7, version: 3, subject: "Welcome", body: "Hello", statuses: ["registered"], attendance: "any", status: "draft", available_at: null, render_schema_version: 2, design: "classic", ctas: [] };
function mount(element: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{element}</QueryClientProvider>); }
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });
it("requires exact server audience confirmation and uses sandboxed previews", async () => {
  vi.mocked(staffRequest).mockImplementation(async path => path.endsWith("preview/") ? { preview_id: 8, revision: "audience-sha", recipient_count: 12, subject: "Welcome", text: "Hello", desktop_html: "<p>Desktop safe content</p>", mobile_html: "<p>Mobile safe content</p>" } : campaign);
  mount(<BroadcastDeliveryControls eventId={42} makerspaceId={9} campaign={campaign} />);
  expect(screen.queryByRole("button", { name: "Schedule broadcast" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Preview audience and message" }));
  expect(await screen.findByText("12 eligible recipients at this revision")).toBeVisible();
  expect(screen.getByTitle("Desktop message preview")).toHaveAttribute("sandbox", "allow-same-origin");
  fireEvent.click(screen.getByRole("button", { name: "Mobile" })); expect(screen.getByTitle("Mobile message preview")).toHaveAttribute("srcdoc", "<p>Mobile safe content</p>");
  expect(screen.getByRole("button", { name: "Schedule broadcast" })).toBeDisabled();
  fireEvent.click(screen.getByRole("checkbox", { name: /I confirm/ })); fireEvent.click(screen.getByRole("button", { name: "Schedule broadcast" }));
  await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([path]) => path.endsWith("schedule/"))).toBe(true));
  const call = vi.mocked(staffRequest).mock.calls.find(([path]) => path.endsWith("schedule/"))!;
  expect(JSON.parse(String(call[1]?.body))).toMatchObject({ expected_version: 3, preview_id: 8, revision: "audience-sha", recipient_count: 12, confirm: true });
});
it("test send never accepts a recipient and reports suppressed delivery honestly", async () => {
  vi.mocked(staffRequest).mockImplementation(async path => path.endsWith("preview/") ? { preview_id: 8, revision: "sha", recipient_count: 1, text: "Hello", desktop_html: "", mobile_html: "" } : { state: "skipped", recipient: "self" });
  mount(<BroadcastDeliveryControls eventId={42} makerspaceId={9} campaign={campaign} />); fireEvent.click(screen.getByRole("button", { name: "Preview audience and message" })); fireEvent.click(await screen.findByRole("button", { name: "Send test to myself" }));
  expect(await screen.findByText(/Test was skipped/)).toBeVisible();
  const call = vi.mocked(staffRequest).mock.calls.find(([path]) => path.endsWith("test/"))!; expect(JSON.parse(String(call[1]?.body))).not.toHaveProperty("recipient");
});
it("keeps retry operation ID after ambiguous create failure", async () => {
  vi.mocked(staffRequest).mockRejectedValue(new Error("Network unavailable")); mount(<BroadcastComposer eventId={42} makerspaceId={9} initial={{ ...campaign, render_schema_version: 2 }} onSaved={() => {}} />);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" })); expect(await screen.findByRole("alert")).toHaveTextContent("Network unavailable");
  const posts = () => vi.mocked(staffRequest).mock.calls.filter(([, options]) => options?.method === "POST");
  fireEvent.click(screen.getByRole("button", { name: "Save draft" })); await waitFor(() => expect(posts()).toHaveLength(2));
  expect(posts()[0][1]?.headers).toEqual(posts()[1][1]?.headers);
});
it("preserves strict empty legacy cancellation bodies", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ ...campaign, render_schema_version: 1, status: "cancelled" });
  mount(<BroadcastDeliveryControls eventId={42} makerspaceId={9} campaign={{ ...campaign, render_schema_version: 1 }} />);
  fireEvent.click(screen.getByRole("button", { name: "Cancel broadcast" })); await waitFor(() => expect(staffRequest).toHaveBeenCalled());
  expect(vi.mocked(staffRequest).mock.calls[0][1]?.body).toBe("{}"); expect(vi.mocked(staffRequest).mock.calls[0][1]?.headers).toBeUndefined();
});
