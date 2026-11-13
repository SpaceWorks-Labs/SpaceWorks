import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberCardsPanel } from "./MemberCardsPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const card = (id: number, name: string) => ({ id, card_number: id, number_display: `TNK-000${id}`, printed_name: name, membership_id: id,
  is_active: true, photo_set: false, photo_consent_at: null, qr_active: true, print_count: 0, last_printed_at: null,
  issued_at: "2026-11-01T10:00:00Z", valid_until: "", photo_request_open: false, last_emailed_at: null, revoked_at: null,
  revoked_reason: "", created_at: "", updated_at: "" });

beforeEach(() => {
  staffRequest.mockReset().mockImplementation((path: string) => Promise.resolve(
    path.includes("/member-cards?") ? { count: 2, next: null, previous: null, results: [card(5, "Priya Raman"), card(6, "Ravi Nair")] }
      : path.includes("member-card-settings") ? { email_available: false, wallet_platforms: [] }
        : path.includes("card-jobs") ? [] : []));
});

function mount(features: string[]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><MemberCardsPanel makerspaceId={4} enabledFeatures={features} /></MemoryRouter></QueryClientProvider>);
}

const openMenu = () => fireEvent.click(screen.getByRole("button", { name: /All cards/ }));
const menuLabel = /Print selected at desk/;

describe("Print selected at desk (member cards)", () => {
  it("is hidden while nothing is ticked, and when desk printing is off", async () => {
    mount(["membership.card_desk_print"]);
    await screen.findByText("Priya Raman");
    openMenu();
    expect(screen.queryByRole("menuitem", { name: menuLabel })).not.toBeInTheDocument();
  });

  it("is hidden with desk printing off even when cards are ticked", async () => {
    mount([]);
    await screen.findByText("Priya Raman");
    screen.getAllByRole("checkbox").slice(1).forEach((box) => fireEvent.click(box));
    openMenu();
    expect(screen.queryByRole("menuitem", { name: menuLabel })).not.toBeInTheDocument();
  });

  it("opens the batch dialog for the ticked cards", async () => {
    mount(["membership.card_desk_print"]);
    await screen.findByText("Priya Raman");
    screen.getAllByRole("checkbox").slice(1).forEach((box) => fireEvent.click(box));
    openMenu();
    fireEvent.click(await screen.findByRole("menuitem", { name: menuLabel }));
    expect(await screen.findByText("Print at the desk")).toBeVisible();
  });
});
