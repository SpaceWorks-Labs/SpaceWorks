import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../../test/axe";
import { MemberCardsPanel } from "./MemberCardsPanel";

const { staffRequest, staffRequestBlob } = vi.hoisted(() => ({
  staffRequest: vi.fn(),
  staffRequestBlob: vi.fn(),
}));

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest, staffRequestBlob };
});

const card = {
  id: 4,
  card_number: 104,
  number_display: "TNK-2026-0104",
  printed_name: "Ada Lovelace",
  membership_id: 11,
  is_active: true,
  photo_set: true,
  photo_consent_at: "2026-08-01T10:00:00Z",
  qr_active: true,
  print_count: 2,
  last_printed_at: "2026-08-20T10:00:00Z",
  issued_at: "2026-07-01T10:00:00Z",
  valid_until: "31 Dec 2026",
  photo_request_open: false,
  last_emailed_at: null,
  revoked_at: null,
  revoked_reason: "",
  created_at: "2026-07-01T10:00:00Z",
  updated_at: "2026-08-20T10:00:00Z",
};

const template = {
  version: 1,
  page: "a4" as const,
  orientation: "portrait" as const,
  card_width_mm: 85.6,
  card_height_mm: 54,
  margin_mm: 10,
  gap_mm: 4,
  front_fields: ["printed_name", "card_number"],
  back_text: "Return to the front desk if found.",
  include_photo: true,
  include_qr: true,
  name_font_size_pt: 14,
  font_size_pt: 9,
  crop_marks: true,
};

// Two memberships: one already carries `card` (id 11) and must NOT appear in the issue
// roster, one has no card (id 12) and must.
const memberships = [
  { id: 11, user: { username: "ada", display_name: "Ada Lovelace" }, status: "active" },
  { id: 12, user: { username: "grace" }, status: "active" },
];

function route(path: string) {
  if (path.includes("member-cards?status=active")) {
    return Promise.resolve({ count: 1, next: null, previous: null, results: [card] });
  }
  if (path.includes("member-cards?status=revoked")) {
    return Promise.resolve({ count: 0, next: null, previous: null, results: [] });
  }
  if (path.endsWith("/memberships")) return Promise.resolve(memberships);
  if (path.endsWith("/member-card-template")) return Promise.resolve(template);
  if (path.endsWith("/member-card-settings")) return Promise.resolve({ auto_issue: true, email_on_issue: false, public_verify: true,
    verify_show_plan: true, design_approval_required: true, email_available: true, photo_cleanup_available: false, wallet_platforms: [] });
  if (path.endsWith("/member-card-jobs")) return Promise.resolve([]);
  return Promise.resolve(card);
}

function renderPanel() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}><MemoryRouter>
      <MemberCardsPanel makerspaceId={7} />
    </MemoryRouter></QueryClientProvider>,
  );
}

beforeEach(() => {
  staffRequest.mockReset();
  staffRequestBlob.mockReset();
  staffRequest.mockImplementation(route);
  staffRequestBlob.mockResolvedValue(new Blob(["pdf"]));
});

describe("MemberCardsPanel", () => {
  it("lists the active cards and the members still without one", async () => {
    const { container } = renderPanel();

    expect(await screen.findByText("TNK-2026-0104")).toBeVisible();
    expect(screen.getByText("31 Dec 2026")).toBeVisible();
    expect(screen.getByText("Ada Lovelace")).toBeVisible();
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("link", { name: "Issue" }));
    // grace holds no card; ada already does, so only grace is offered an issue button.
    expect(await screen.findByText("grace")).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Issue card" })).toHaveLength(1);

    await expectNoA11yViolations(container);
  });

  it("labels the print button with the selected count as one translated message (ID-4)", async () => {
    renderPanel();
    expect(await screen.findByText("TNK-2026-0104")).toBeVisible();
    expect(screen.getByRole("button", { name: "Print all active" })).toBeVisible();
    const boxes = screen.getAllByRole("checkbox");
    fireEvent.click(boxes[boxes.length - 1]);
    expect(await screen.findByRole("button", { name: "Print sheet (1 selected)" })).toBeVisible();
  });

  it("issues a card for the selected membership", async () => {
    renderPanel();

    fireEvent.click(await screen.findByRole("link", { name: "Issue" }));
    fireEvent.click(await screen.findByRole("button", { name: "Issue card" }));

    await waitFor(() =>
      expect(staffRequest).toHaveBeenCalledWith(
        "/admin/makerspaces/7/member-cards/12/issue",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });

  it("asks for confirmation before revoking a card", async () => {
    renderPanel();

    fireEvent.click(await screen.findByRole("button", { name: "Actions for Ada Lovelace" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Revoke…" }));

    // The dialog is up and nothing has been sent yet.
    expect(await screen.findByRole("dialog")).toBeVisible();
    expect(staffRequest).not.toHaveBeenCalledWith(
      "/admin/member-cards/4/revoke",
      expect.anything(),
    );

    // The note is required before the revoke can be sent.
    expect(screen.getByRole("button", { name: "Revoke card" })).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Why is it revoked?" }), { target: { value: "Card lost twice" } });
    fireEvent.click(screen.getByRole("button", { name: "Revoke card" }));

    await waitFor(() =>
      expect(staffRequest).toHaveBeenCalledWith(
        "/admin/member-cards/4/revoke",
        expect.objectContaining({ method: "POST", body: JSON.stringify({ note: "Card lost twice" }) }),
      ),
    );
  });

  it("starts a bulk ZIP job from the All cards menu", async () => {
    renderPanel();
    await screen.findByText("TNK-2026-0104");
    fireEvent.click(screen.getByRole("button", { name: /All cards/ }));
    fireEvent.click(await screen.findByRole("menuitem", { name: "All cards (ZIP)" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/member-card-jobs",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ kind: "zip", status: "active" }) })));
  });

  it("downloads one card as PNG from the row menu", async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Actions for Ada Lovelace" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Download PNG" }));
    await waitFor(() => expect(staffRequestBlob).toHaveBeenCalledWith("/admin/member-cards/4/download?format=png&side=front"));
  });

  it("prints a single card through the blob endpoint", async () => {
    renderPanel();

    fireEvent.click(await screen.findByRole("button", { name: "Print" }));

    await waitFor(() =>
      expect(staffRequestBlob).toHaveBeenCalledWith(
        "/admin/member-cards/4/print.pdf",
        expect.objectContaining({ method: "POST" }),
      ),
    );
  });
});


it("keeps the Active/Revoked status visible beside the filters and reflects the choice", async () => {
  renderPanel();
  await screen.findByText("TNK-2026-0104");
  const active = screen.getByRole("radio", { name: "Active" });
  expect(active).toHaveAttribute("aria-checked", "true");
  fireEvent.click(screen.getByRole("radio", { name: "Revoked" }));
  expect(screen.getByRole("radio", { name: "Revoked" })).toHaveAttribute("aria-checked", "true");
  expect(await screen.findByText("No revoked cards.")).toBeVisible();
});
