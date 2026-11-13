import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemberAccountDeletion, AccountDeletionReceipt } from "./MemberAccountDeletion";
import { AccountDeletionReauthentication } from "./AccountDeletionReauthentication";
import { StructuredApiError } from "../../lib/api/errors";
import { expectNoA11yViolations } from "../../test/axe";
import type { DeletionPreview } from "./accountDeletionApi";

const mocks = vi.hoisted(() => ({ request: vi.fn(), clear: vi.fn(), forget: vi.fn(), social: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: mocks.request, staffRequest: mocks.request, clearAccessToken: mocks.clear, getAccessToken: () => "" }));
vi.mock("./memberCard/offlineCard", () => ({ forgetOfflineMemberData: mocks.forget }));
vi.mock("../auth/reauthenticationSocial", () => ({ reauthenticateMemberSocial: mocks.social }));

let preview: DeletionPreview;
let client: QueryClient;
const result = { deleted_at: "2026-10-17T00:00:00Z", purge_after: "2027-01-15T00:00:00Z" };
function mount(element = <MemberAccountDeletion slug="current" onDeleted={vi.fn()} />) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}
beforeEach(() => {
  vi.clearAllMocks();
  preview = { deletable: true, restorable: true, restore_reason: "Use password recovery before the purge deadline.", blockers: [], reauth: { required: false, methods: ["password"] } };
  mocks.request.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === "/auth/account/deletion") return options?.method === "POST" ? result : preview;
    if (path === "/auth/reauth/phone/start") return { sent: true, token: "phone-intent" };
    preview = { ...preview, reauth: { ...preview.reauth, required: false } };
    return { verified: true, expires_in: 600 };
  });
});

describe("account deletion", () => {
  it("discloses non-restorable provider accounts before confirmation", async () => {
    preview = { ...preview, restorable: false, restore_reason: "Your provider cannot prove fresh authentication; this account cannot be restored." };
    mount();
    expect(await screen.findByText(/This account cannot be restored: Your provider cannot prove fresh authentication/)).toBeInTheDocument();
    expect(screen.getByLabelText("Type DELETE to confirm")).toBeInTheDocument();
  });
  it("requires exact typed confirmation, then clears identity and private caches", async () => {
    const onDeleted = vi.fn();
    mount(<MemberAccountDeletion slug="current" onDeleted={onDeleted} />);
    const confirm = await screen.findByLabelText("Type DELETE to confirm");
    const button = screen.getByRole("button", { name: "Delete account permanently" });
    expect(button).toBeDisabled();
    fireEvent.change(confirm, { target: { value: "delete" } });
    expect(button).toBeDisabled();
    fireEvent.change(confirm, { target: { value: "DELETE" } });
    client.setQueryData(["member", "private-records"], ["personal"]);
    fireEvent.click(button);
    await waitFor(() => expect(onDeleted).toHaveBeenCalledWith(result));
    expect(mocks.request).toHaveBeenCalledWith("/auth/account/deletion", expect.objectContaining({ method: "POST", body: '{"confirm":"DELETE"}' }));
    expect(mocks.clear).toHaveBeenCalledOnce();
    expect(mocks.forget).toHaveBeenCalledOnce();
    expect(client.getQueryData(["member", "private-records"])).toBeUndefined();
  });

  it("links blockers to their owning makerspace and hides confirmation", async () => {
    preview = { ...preview, deletable: false, blockers: [{ code: "upcoming_bookings", makerspace_id: 7, makerspace_slug: "other-space", organization_id: null, count: 2, detail: "Cancel upcoming bookings." }] };
    const { container } = mount();
    expect(await screen.findByRole("link", { name: "Manage bookings" })).toHaveAttribute("href", "/m/other-space/member/bookings");
    expect(screen.queryByLabelText("Type DELETE to confirm")).not.toBeInTheDocument();
    await expectNoA11yViolations(container);
  });

  it("requires password reauthentication before deletion", async () => {
    preview.reauth.required = true;
    mount();
    const password = await screen.findByLabelText("Current password");
    fireEvent.change(screen.getByLabelText("Type DELETE to confirm"), { target: { value: "DELETE" } });
    expect(screen.getByRole("button", { name: "Delete account permanently" })).toBeDisabled();
    fireEvent.change(password, { target: { value: "fresh-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify identity for deletion" }));
    await screen.findByText("Your recent sign-in is confirmed.");
    expect(mocks.request).toHaveBeenCalledWith("/auth/reauth", expect.objectContaining({ body: '{"password":"fresh-password","code":""}' }));
    expect(screen.getByRole("button", { name: "Delete account permanently" })).toBeEnabled();
  });

  it("shows the contact fallback when no reauthentication method is usable", async () => {
    preview.reauth = { required: true, methods: [] };
    const { container } = mount();
    await screen.findByText(/There is no available sign-in method/);
    expect(screen.queryByRole("button", { name: "Verify identity for deletion" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete account permanently" })).toBeDisabled();
    await expectNoA11yViolations(container);
  });

  it("uses the server's verified domain for another makerspace's blocker", async () => {
    preview = { ...preview, deletable: false, blockers: [{ code: "active_loans", makerspace_id: 9,
      makerspace_slug: "elsewhere", makerspace_member_url: "https://elsewhere.example.test/member",
      organization_id: null, count: 1, detail: "Return borrowed hardware." }] };
    mount();
    expect(await screen.findByRole("link", { name: "View borrowed hardware" })).toHaveAttribute("href", "https://elsewhere.example.test/member/loans");
  });

  it("handles a server-side race by showing refreshed blockers", async () => {
    const onDeleted = vi.fn();
    const original = mocks.request.getMockImplementation()!;
    mocks.request.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === "/auth/account/deletion" && options?.method === "POST") {
        preview = { ...preview, deletable: false, blockers: [{ code: "unpaid_charges", makerspace_id: 1, makerspace_slug: "other", organization_id: null, count: 1, detail: "Settle a new charge." }] };
        throw new StructuredApiError(409, { blockers: preview.blockers });
      }
      return original(path, options);
    });
    mount(<MemberAccountDeletion slug="current" onDeleted={onDeleted} />);
    fireEvent.change(await screen.findByLabelText("Type DELETE to confirm"), { target: { value: "DELETE" } });
    fireEvent.click(screen.getByRole("button", { name: "Delete account permanently" }));
    await screen.findByRole("link", { name: "View charges" });
    expect(onDeleted).not.toHaveBeenCalled();
    expect(mocks.clear).not.toHaveBeenCalled();
  });

  it("shows a retry for preview failures", async () => {
    mocks.request.mockRejectedValueOnce(new Error("Temporarily unavailable"));
    mount();
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: "Retry deletion check" }));
    await screen.findByLabelText("Type DELETE to confirm");
  });

  it("renders the signed-out result and delayed purge date", async () => {
    const { container } = render(<AccountDeletionReceipt result={result} />);
    expect(screen.getByRole("status")).toHaveTextContent("signed out on all devices");
    expect(screen.getByRole("heading", { name: "Account deletion requested" })).toBeInTheDocument();
    await expectNoA11yViolations(container);
  });
});

describe("deletion reauthentication methods", () => {
  it("verifies a phone-only account with a bound code", async () => {
    const verified = vi.fn();
    mount(<AccountDeletionReauthentication methods={["phone"]} onVerified={verified} />);
    fireEvent.click(screen.getByRole("button", { name: "Send phone verification code" }));
    fireEvent.change(await screen.findByLabelText("Verification code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify identity for deletion" }));
    await waitFor(() => expect(verified).toHaveBeenCalledOnce());
    expect(mocks.request).toHaveBeenCalledWith("/auth/reauth/phone/confirm", expect.objectContaining({ body: '{"token":"phone-intent","code":"123456"}' }));
  });

  it("finishes a provider's emailed second factor in the same intent", async () => {
    mocks.social.mockResolvedValue({ verified: false, factor_required: "email_code", factor_token: "bound-factor", expires_in: 600 });
    const verified = vi.fn();
    const { container } = mount(<AccountDeletionReauthentication methods={["github"]} onVerified={verified} />);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Confirm with github" })); });
    fireEvent.change(await screen.findByLabelText("Verification code"), { target: { value: "234567" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify identity for deletion" }));
    await waitFor(() => expect(verified).toHaveBeenCalledOnce());
    expect(mocks.request).toHaveBeenCalledWith("/auth/reauth/social/factor", expect.objectContaining({ body: '{"token":"bound-factor","code":"234567"}' }));
    await expectNoA11yViolations(container);
  });
});
