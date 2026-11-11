import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DonatePage } from "./DonatePage";
import type { DonationPage } from "./donationsApi";

const { tenantPublicRequest, getAccessToken, memberRequest } = vi.hoisted(() => ({
  tenantPublicRequest: vi.fn(), getAccessToken: vi.fn(() => null as string | null), memberRequest: vi.fn(),
}));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), tenantPublicRequest, getAccessToken, memberRequest,
}));
vi.mock("./DonationShell", () => ({
  useDonationSpace: () => ({ slug: "lab", bootstrap: undefined, path: (part = "") => `/m/lab/${part}` }),
  DonationShell: ({ title, children }: { title: string; children: ReactNode }) => <main><h1>{title}</h1>{children}</main>,
}));

const page: DonationPage = {
  makerspace: "The Lab", intro: "Keep the lights on.", currency: "inr", minimum_amount: "10.00", suggested_amounts: ["500", "1000"],
  campaigns: [{ id: 4, kind: "campaign", name: "New laser", slug: "laser", description: "", goal_amount: "10000.00",
    raised_amount: "2500.00", currency: "inr", starts_at: null, ends_at: null }],
  online_available: true, recurring_available: false, tax_receipts_available: false, tax_registration_number: "", guest_allowed: true,
};
const fetchMock = vi.fn();
const assign = vi.fn();

function show(data: DonationPage = page) {
  tenantPublicRequest.mockResolvedValue(data);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}><DonatePage /></QueryClientProvider></MemoryRouter>);
}
const reply = (status: number, body: unknown) => Promise.resolve(new Response(status === 202 ? null : JSON.stringify(body), { status }));

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  Object.defineProperty(window, "location", { configurable: true, value: { ...window.location, assign } });
  getAccessToken.mockReturnValue(null);
});
afterEach(() => { vi.unstubAllGlobals(); fetchMock.mockReset(); assign.mockReset(); tenantPublicRequest.mockReset(); });

describe("DonatePage", () => {
  it("lets a guest confirm their email with a code and sends it with the gift, then opens checkout", async () => {
    fetchMock.mockImplementation((url: string) => url.endsWith("/email-code") ? reply(202, null)
      : reply(201, { checkout_url: "https://pay.example/session", status_token: "tok" }));
    show();
    expect(await screen.findByRole("heading", { name: "Support The Lab" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "₹500.00" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Your name" }), { target: { value: "Grace" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Email" }), { target: { value: "grace@example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Email me a code" }));
    const code = await screen.findByRole("textbox", { name: "Code from the email" });
    fireEvent.change(code, { target: { value: "246810" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue to payment" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://pay.example/session"));
    const give = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/public/lab/donations/give"))!;
    expect(JSON.parse(give[1].body)).toMatchObject({ amount: "500", donor_name: "Grace", donor_email: "grace@example.test",
      email_code: "246810", campaign: null });
    expect(JSON.parse(give[1].body)).not.toHaveProperty("donor_pan");
  });

  it("asks for a PAN only where 80G receipts are offered and only once one is wanted", async () => {
    const view = show();
    await screen.findByRole("heading", { name: "Support The Lab" });
    expect(screen.queryByRole("checkbox", { name: /tax receipt/ })).not.toBeInTheDocument();
    view.unmount();
    show({ ...page, tax_receipts_available: true, tax_registration_number: "AAATS1234F20240",
      tax_schemes: ["India: section 80G"], tax_receipt_needs_pan: true });
    const wants = await screen.findByRole("checkbox", { name: /tax receipt \(India: section 80G, registration AAATS1234F20240\)/ });
    expect(screen.queryByRole("textbox", { name: "PAN" })).not.toBeInTheDocument();
    fireEvent.click(wants);
    expect(screen.getByRole("textbox", { name: "PAN" })).toBeRequired();
  });

  // Decision 242(m): other schemes ask for nothing more; without a profile the receipt says what it is.
  it("asks no PAN for a 501(c)(3) receipt and says when there is no tax receipt", async () => {
    const view = show({ ...page, tax_receipts_available: true, tax_registration_number: "12-3456789",
      tax_schemes: ["United States: 501(c)(3)"], tax_receipt_needs_pan: false,
      nonprofit: { is_nonprofit: true, legal_name: "Lab Trust", registration_number: "", exemptions: [
        { scheme: "us_501c3", label: "United States: 501(c)(3)", number: "12-3456789" }] } });
    fireEvent.click(await screen.findByRole("checkbox", { name: /tax receipt/ }));
    expect(screen.queryByRole("textbox", { name: "PAN" })).not.toBeInTheDocument();
    expect(screen.getByText(/Lab Trust, a non-profit/)).toBeInTheDocument();
    view.unmount();
    show({ ...page, receipt_note: "This is a receipt for your gift. It is not a tax receipt." });
    expect(await screen.findByText("This is a receipt for your gift. It is not a tax receipt.")).toBeInTheDocument();
  });

  it("names a giver on the campaign page only when they opt in", async () => {
    fetchMock.mockImplementation(() => reply(201, { checkout_url: "", status_token: "tok" }));
    getAccessToken.mockReturnValue("member-token");
    memberRequest.mockResolvedValue({ checkout_url: "", status_token: "", id: 1, status: "pending", makerspace: "The Lab",
      campaign: "New laser", amount: "50.00", currency: "inr", payment_status: "pending", created_at: "2026-11-01T00:00:00Z",
      paid_at: null, receipt_number: "", tax_receipt_number: "", donor_pan_masked: "", online_available: false, offline: null });
    show();
    await screen.findByRole("heading", { name: "Support The Lab" });
    expect(screen.queryByRole("checkbox", { name: /Name me/ })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /New laser/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /Name me among this campaign's supporters/ }));
    fireEvent.change(screen.getByRole("textbox", { name: /Amount/ }), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue to payment" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalled());
    expect(JSON.parse(memberRequest.mock.calls[0][1].body)).toMatchObject({ campaign: 4, recognize_publicly: true });
  });

  it("gives as the signed-in member without asking who they are", async () => {
    getAccessToken.mockReturnValue("member-token");
    memberRequest.mockResolvedValue({ checkout_url: "", status_token: "", id: 1, status: "pending", makerspace: "The Lab",
      campaign: "", amount: "50.00", currency: "inr", payment_status: "pending", created_at: "2026-11-01T00:00:00Z",
      paid_at: null, receipt_number: "", tax_receipt_number: "", donor_pan_masked: "", online_available: false, offline: null });
    show();
    await screen.findByRole("heading", { name: "Support The Lab" });
    expect(screen.queryByRole("textbox", { name: "Email" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: /Amount/ }), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue to payment" }));
    expect(await screen.findByText("Waiting for payment")).toBeInTheDocument();
    expect(memberRequest).toHaveBeenCalledWith("/public/lab/donations/give", expect.objectContaining({ method: "POST" }));
  });

  it("explains when the space takes no donations", async () => {
    const { StructuredApiError } = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
    tenantPublicRequest.mockRejectedValue(new StructuredApiError(404, { code: "feature_disabled" }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<MemoryRouter><QueryClientProvider client={client}><DonatePage /></QueryClientProvider></MemoryRouter>);
    expect(await screen.findByText(/isn't taking donations online/)).toBeInTheDocument();
  });
});
