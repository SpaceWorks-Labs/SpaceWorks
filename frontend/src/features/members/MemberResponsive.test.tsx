import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render as rtlRender, screen, within } from "@testing-library/react";
// Screens now read query-backed switches (help-centre bootstrap, #184 charge flags), so every render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import offlineHtml from "../../../public/member-pwa/offline.html?raw";
import { MemberCardPanel } from "./MemberCardPanel";
import { MemberPaymentRows, type MemberPayment } from "./MemberPayments";
import { MemberPortalTabs } from "./MemberPortalTabs";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../lib/api")>("../../lib/api");
  return { ...actual, memberRequest };
});

const card = { id: 3, card_number: 103, printed_name: "Grace Hopper", membership_id: 12, is_active: true, photo_set: false,
  photo_consent_at: null, qr_active: true, qr_image: "data:image/png;base64,eA==", print_count: 1, last_printed_at: null,
  issued_at: "2026-07-01T10:00:00Z", revoked_at: null, revoked_reason: "", created_at: "2026-07-01T10:00:00Z", updated_at: "2026-07-01T10:00:00Z" };

function renderCard(compact = false) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemberCardPanel makerspaceId={5} compact={compact} /></QueryClientProvider>);
}

beforeEach(() => { localStorage.clear(); memberRequest.mockReset(); });

describe("member card at scanning size", () => {
  it.each([false, true])("opens the QR full-size in a dialog with a reachable close (compact %s)", async compact => {
    memberRequest.mockResolvedValue(card);
    renderCard(compact);
    fireEvent.click(await screen.findByRole("button", { name: "Show QR to scan" }));
    const dialog = screen.getByRole("dialog", { name: "Scan your member card" });
    const qr = within(dialog).getByRole("img", { name: "Member card QR code for Grace Hopper" });
    // Fills the dialog in portrait, is capped by the viewport height in landscape, and keeps module edges crisp.
    expect(qr.className).toContain("w-full");
    expect(qr.className).toContain("calc(100dvh-12rem)");
    expect(qr.className).toContain("[image-rendering:pixelated]");
    fireEvent.click(within(dialog).getByRole("button", { name: "Done" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("offers no scan view for a revoked card", async () => {
    memberRequest.mockResolvedValue({ ...card, is_active: false, qr_active: false, qr_image: null });
    renderCard();
    await screen.findByText("This card was revoked.");
    expect(screen.queryByRole("button", { name: "Show QR to scan" })).not.toBeInTheDocument();
  });
});

describe("payment rows on a phone", () => {
  const base = { id: 5, subject_type: "loan_deposit", subject_label: "Loan deposit - request #12", status: "pending", amount: "10.00",
    currency: "usd", due_date: null, due_state: "none", checkout_url: "", online_payment_available: true, settlement: null,
    refunds: [], created_at: "2026-10-01T10:00:00Z" } as unknown as MemberPayment;

  it("puts the pay action on its own full-width line and keeps the title readable", () => {
    const { container } = render(<MemberPaymentRows onCheckout={vi.fn()} payments={[{ ...base, checkout_url: "https://pay.test/x" },
      { ...base, id: 6, online_payment_available: false }]} />);
    const pay = screen.getByRole("link", { name: "Pay now" });
    expect(pay).toHaveClass("w-full", "sm:w-auto");
    expect(pay.parentElement).toHaveClass("mt-3", "flex");
    expect(screen.getByText("Pay at the space")).toBeInTheDocument();
    expect(container.querySelector("ul")?.className).toContain("[&>li>div>:first-child]:basis-48");
  });
});

describe("member shell content", () => {
  it("lifts sticky save bars above the bottom tabs and keeps focused fields clear of them", () => {
    render(<MemoryRouter initialEntries={["/member"]}><MemberPortalTabs modules={[]} active="overview" user={{ name: "Ada", menu: [] }}>
      <p>Body</p></MemberPortalTabs></MemoryRouter>);
    const wrapper = screen.getByText("Body").parentElement!;
    expect(wrapper.className).toContain("[&_.sticky.bottom-0]:bottom-[calc(var(--shell-bottom-tabs,0px)+env(safe-area-inset-bottom,0px))]");
    expect(wrapper.className).toContain("lg:[&_.sticky.bottom-0]:bottom-0");
    expect(wrapper.className).toContain("[&_:is(input,select,textarea)]:scroll-mb-28");
  });
});

describe("offline member page", () => {
  it("runs edge to edge on iOS without text under the notch or home bar", () => {
    expect(offlineHtml).toContain("viewport-fit=cover");
    expect(offlineHtml).toContain("env(safe-area-inset-top)");
    expect(offlineHtml).toContain("env(safe-area-inset-bottom)");
    expect(offlineHtml).toContain("min-height: 100dvh");
    expect(offlineHtml).not.toMatch(/100vh;\s*}/);
  });

  it("keeps the saved QR on screen in phone landscape", () => {
    expect(offlineHtml).toMatch(/@media \(orientation: landscape\) and \(max-height: 500px\)[\s\S]*#card img \{ width: min\(100%, calc\(100dvh - 3rem\)\)/);
  });
});
