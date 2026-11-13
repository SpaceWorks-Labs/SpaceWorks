import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { AdmissionJoin } from "./AdmissionJoin";
import { MemberCardPanel } from "./MemberCardPanel";
import type { PublicAdmission } from "./membershipAdmissionApi";

// MOD-3B frontend states for membership join and the member card: loading, error, empty, permission denied,
// module-off (closed / invite-only), disabled-while-pending and keyboard submit.
const { memberRequest, memberRequestBlob } = vi.hoisted(() => ({ memberRequest: vi.fn(), memberRequestBlob: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"),
  memberRequest, memberRequestBlob }));

const settings: PublicAdmission = {
  join_mode: "approval", vouches_required: 0, payment_timing: "after_activation",
  application_schema: [{ id: "motivation", label: "Why join?", type: "paragraph", options: [], required: true }],
  default_plan: null, joining_fee: "0.00",
};
const join = (over: Partial<Parameters<typeof AdmissionJoin>[0]> = {}) => render(<AdmissionJoin settings={settings} signedIn pending={false}
  onJoin={vi.fn()} onSignIn={vi.fn()} {...over} />);

describe("AdmissionJoin states", () => {
  it("closed: shows the closed heading and offers no form or button at all", () => {
    join({ settings: { ...settings, join_mode: "closed" } });
    expect(screen.getByRole("heading", { name: "Membership applications are closed" })).toBeVisible();
    expect(screen.getByText("This makerspace is not accepting new members.")).toBeVisible();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("invite-only without a valid invite: asks for an invitation and offers no submit", () => {
    join({ settings: { ...settings, join_mode: "invite_only" }, invite: { valid: false, plan_id: null, plan_name: "", label: "" } });
    expect(screen.getByRole("heading", { name: "Invite-only makerspace" })).toBeVisible();
    expect(screen.getByText("Ask a space manager for an invitation.")).toBeVisible();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("pending: the submit button says Sending and the question is locked so it cannot be sent twice", () => {
    join({ pending: true });
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDisabled();
    expect(screen.getByLabelText(/Why join/)).toBeDisabled();
  });

  it("error: a server failure is announced as an alert with its message", () => {
    join({ error: new Error("Applications are paused.") });
    expect(screen.getByRole("alert")).toHaveTextContent("Applications are paused.");
  });

  it("error that is not an Error object falls back to the generic message", () => {
    join({ error: "boom" });
    expect(screen.getByRole("alert")).toHaveTextContent("Unable to submit your application.");
  });

  it("a server-side answer error shows against the question, not only as a banner", () => {
    join({ error: new StructuredApiError(400, { code: "validation_error", detail: "bad", application_answers: { motivation: ["Too short."] } }) });
    expect(screen.getByText("Too short.")).toBeVisible();
  });

  it("keyboard: submitting a filled form sends it once; an empty required answer blocks it", () => {
    const onJoin = vi.fn();
    join({ onJoin, settings: { ...settings, application_schema: [{ id: "nick", label: "Nickname", type: "short_text", options: [], required: true }] } });
    const field = screen.getByLabelText(/Nickname/);
    fireEvent.submit(field.closest("form")!);
    expect(onJoin).not.toHaveBeenCalled();
    expect(screen.getByText("This question is required.")).toBeVisible();
    fireEvent.change(field, { target: { value: "Ada" } });
    fireEvent.submit(field.closest("form")!);
    expect(onJoin).toHaveBeenCalledTimes(1);
    expect(onJoin).toHaveBeenCalledWith({ nick: "Ada" }, {});
  });

  it("charges off: no plan, joining fee or payment copy is shown when prices are hidden", () => {
    join({ showPrice: false, settings: { ...settings, joining_fee: "25.00", default_plan: { id: 1, name: "Community", amount: "10.00", currency: "usd" } } });
    expect(screen.queryByText(/Joining fee/)).toBeNull();
    expect(screen.queryByText(/\$10\.00/)).toBeNull();
    expect(screen.queryByText(/Payment is required/)).toBeNull();
  });
});

const CARD = "/member/makerspaces/5/member-card";
const card = { id: 3, card_number: 103, printed_name: "Grace Hopper", membership_id: 12, is_active: true, photo_set: false,
  photo_consent_at: null, qr_active: true, print_count: 1, last_printed_at: null, issued_at: "2026-07-01T10:00:00Z", revoked_at: null,
  revoked_reason: "", created_at: "2026-07-01T10:00:00Z", updated_at: "2026-08-20T10:00:00Z", qr_image: "data:image/png;base64,eA==" };
const panel = (props: Partial<Parameters<typeof MemberCardPanel>[0]> = {}) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemberCardPanel makerspaceId={5} {...props} /></QueryClientProvider>);
};

beforeEach(() => { memberRequest.mockReset(); localStorage.clear(); });

describe("MemberCardPanel states", () => {
  it("loading: shows the loading label and no card details", () => {
    memberRequest.mockReturnValue(new Promise(() => {}));
    panel();
    expect(screen.getByText("Loading your card…")).toBeInTheDocument();
    expect(screen.queryByText("Grace Hopper")).not.toBeInTheDocument();
  });

  it("server error (500): shows the message in an alert and no editor", async () => {
    memberRequest.mockRejectedValue(new StructuredApiError(500, { detail: "Card service is down." }));
    panel();
    expect(await screen.findByRole("alert")).toHaveTextContent("Card service is down.");
    expect(screen.queryByLabelText("Name printed on the card")).not.toBeInTheDocument();
  });

  it("non-Error failure falls back to the generic load message", async () => {
    memberRequest.mockRejectedValue("offline");
    panel();
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load your card.");
  });

  it("compact: a link to the full card replaces the editor", async () => {
    memberRequest.mockResolvedValue(card);
    panel({ compact: true });
    expect(await screen.findByRole("link", { name: "View your member card" })).toHaveAttribute("href", "/member/account-portal?section=card");
    expect(screen.queryByLabelText("Name printed on the card")).not.toBeInTheDocument();
  });

  it("revoked card: no QR is offered as scannable and the revoked callout is shown", async () => {
    memberRequest.mockResolvedValue({ ...card, is_active: false, revoked_at: "2026-09-01T00:00:00Z" });
    panel();
    expect(await screen.findByText("This card was revoked.")).toBeVisible();
    expect(screen.queryByRole("img", { name: "Your member card QR code" })).not.toBeInTheDocument();
  });

  it("keyboard: the printed name is reachable by label, a blank name disables Save, and a failed save is announced", async () => {
    memberRequest.mockImplementation((_path: string, init?: { method?: string }) => init?.method === "PATCH"
      ? Promise.reject(new Error("Name already used.")) : Promise.resolve(card));
    panel();
    const input = await screen.findByLabelText("Name printed on the card");
    input.focus();
    expect(input).toHaveFocus();
    fireEvent.change(input, { target: { value: "   " } });
    expect(screen.getByRole("button", { name: "Save name" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "Grace B. Hopper" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    expect(await screen.findByText("Name already used.")).toBeVisible();
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(CARD, expect.objectContaining({ method: "PATCH" })));
  });
});
