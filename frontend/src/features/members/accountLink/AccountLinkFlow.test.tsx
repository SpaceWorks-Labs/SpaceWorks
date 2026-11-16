import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import { expectNoA11yViolations } from "../../../test/axe";
import { AccountLinkCard } from "./AccountLinkCard";
import type { MergePreview, MergeResult } from "./accountLinkApi";

vi.mock("../../../lib/api", async () => ({ ...await vi.importActual("../../../lib/api"), memberRequest: vi.fn() }));

const base = "/auth/account-merge";
const intent = (method = "credentials", state = "pending") => ({ intent_id: "i-1", method, state, expires_at: "2026-11-03T12:00:00Z" });
const lab = { id: 7, slug: "lab", name: "Lab Space" };
const preview = (grace = false): MergePreview => ({ source: { id: 2, username: "old-staff", display_name: "Ada (staff)" },
  privilege_diff: { roles_gained: [{ makerspace: lab, roles: ["space_manager"] }], duplicate_staff_rows: [] }, grace_opens: grace,
  moves: { repoint: { rows: 12 }, keep_on_shell: { rows: 3 }, unique_resolve: { rows: 2, kept_on_shell: 1 } },
  conflicts: [{ model: "MemberProfile", field: "phone", kept_on_shell: true }], preview_sha256: "abc123", expires_at: "2026-11-03T12:00:00Z" });
const merged = (grace = false): MergeResult => ({ merged: true, record_id: 9, roles_gained: [{ makerspace: lab, roles: ["space_manager"] }], grace_opened: grace,
  counts: { repointed: 12, kept_on_shell: 3, unique_moved: 1, unique_kept: 1, revoked: 2 } });

function api(answers: Record<string, unknown> = {}) {
  const defaults: Record<string, unknown> = { start: intent(), prove: intent("credentials", "proved"), resend: intent("email_codes"),
    preview: preview(), confirm: merged(), cancel: intent("credentials", "cancelled") };
  vi.mocked(memberRequest).mockImplementation(async (path: string, options?: RequestInit) => {
    const action = path.split("/").pop() ?? "";
    const answer = typeof answers[action] === "function" ? (answers[action] as (o?: RequestInit) => unknown)(options) : answers[action] ?? defaults[action];
    if (answer instanceof Error) throw answer;
    return answer;
  });
}
const failure = (status: number, code: string) => new StructuredApiError(status, { code });
const post = (path: string, body?: object) => [`${base}${path}`, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) }];

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><MemoryRouter><AccountLinkCard /></MemoryRouter></QueryClientProvider>);
  return { invalidate };
}
async function startWith(identifier = "old-staff") {
  fireEvent.click(screen.getByRole("button", { name: "Link an account" }));
  fireEvent.change(await screen.findByRole("textbox", { name: "Username or email of the other account" }), { target: { value: identifier } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}
async function proveCredentials() {
  fireEvent.change(await screen.findByLabelText("Password of the other account"), { target: { value: "hunter22" } });
  fireEvent.change(screen.getByRole("textbox", { name: "Authenticator code" }), { target: { value: "123 456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify" }));
}

beforeEach(() => { vi.resetAllMocks(); });

describe("Link your staff account", () => {
  it("starts, proves, previews the roles gained and confirms with the preview hash", async () => {
    api();
    const { invalidate } = show();
    await startWith();
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/start", { identifier: "old-staff", method: "credentials" })));
    await proveCredentials();
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/i-1/prove", { password: "hunter22", otp: "123456" })));
    expect(await screen.findByText("Lab Space")).toBeVisible();
    expect(screen.getByText("Space manager")).toBeVisible();
    expect(screen.getByText("MemberProfile")).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith(`${base}/i-1/preview`);
    fireEvent.click(screen.getByRole("button", { name: "Continue to confirm" }));
    const link = await screen.findByRole("button", { name: "Link accounts" });
    expect(link).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: /stops signing in and this can't be undone/ }));
    fireEvent.click(screen.getByRole("button", { name: "Link accounts" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/i-1/confirm", { preview_sha256: "abc123" })));
    expect(await screen.findByRole("heading", { name: "Accounts linked" })).toBeVisible();
    expect(screen.getByText("Records moved").nextSibling).toHaveTextContent("12");
    expect(screen.getByRole("button", { name: "Back to your account" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open the staff console" })).toHaveAttribute("href", "/admin");
    for (const queryKey of [["member"], ["staff", "me"], ["member", "account", "me"]]) expect(invalidate).toHaveBeenCalledWith({ queryKey });
    expect(vi.mocked(memberRequest).mock.calls.some(([path]) => path.endsWith("/cancel"))).toBe(false);
  });

  it("offers the emailed codes when the other account has no authenticator", async () => {
    api({ prove: failure(409, "factor_enrolment_required"), start: (options?: RequestInit) => intent(JSON.parse(String(options?.body)).method) });
    show();
    await startWith();
    await proveCredentials();
    expect(await screen.findByText("The other account has no authenticator. Use the emailed codes instead.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Use emailed codes instead/ }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/i-1/cancel")));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/start", { identifier: "old-staff", method: "email_codes" })));
    expect(await screen.findByRole("textbox", { name: "Code sent to this account's email" })).toBeVisible();
    expect(screen.getByRole("textbox", { name: "Code sent to the other account's email" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Send new codes" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/i-1/resend")));
    expect(await screen.findByText("New codes sent. Earlier codes no longer work.")).toBeVisible();
  });

  it("shows the mismatch copy when the proof fails", async () => {
    api({ prove: failure(400, "proof_failed") });
    show();
    await startWith();
    await proveCredentials();
    expect(await screen.findByRole("alert")).toHaveTextContent("That didn't match. Check and try again.");
    expect(screen.getByLabelText("Password of the other account")).toBeVisible();
  });

  it("explains the two-step grace window and leads with setting it up", async () => {
    api({ preview: preview(true), confirm: merged(true) });
    show();
    await startWith();
    await proveCredentials();
    expect(await screen.findByText(/You have 3 days to set it up before staff screens are blocked/)).toBeVisible();
    expect(screen.getByRole("link", { name: /Set up two-step sign-in now/ })).toHaveAttribute("href", "/mfa");
    fireEvent.click(screen.getByRole("button", { name: "Continue to confirm" }));
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Link accounts" }));
    expect(await screen.findByRole("link", { name: "Set up two-step sign-in" })).toHaveAttribute("href", "/mfa");
    expect(screen.getByRole("button", { name: "Back to your account" })).toBeVisible();
  });

  it("asks for a fresh preview when the server says it changed", async () => {
    let previews = 0;
    api({ preview: () => { previews += 1; return preview(); }, confirm: failure(409, "preview_stale") });
    show();
    await startWith();
    await proveCredentials();
    await screen.findByText("Lab Space");
    fireEvent.click(screen.getByRole("button", { name: "Continue to confirm" }));
    fireEvent.click(await screen.findByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Link accounts" }));
    expect(await screen.findByText("Something changed. Review again.")).toBeVisible();
    await waitFor(() => expect(previews).toBe(2));
    expect(await screen.findByRole("button", { name: "Continue to confirm" })).toBeVisible();
  });

  it("cancels the link request on the server when the person leaves", async () => {
    api();
    show();
    await startWith();
    await screen.findByLabelText("Password of the other account");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.click(await screen.findByRole("button", { name: "Leave task" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith(...post("/i-1/cancel")));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("has no WCAG violations on the start and review steps", async () => {
    api();
    show();
    await expectNoA11yViolations(document.body);
    await startWith();
    await proveCredentials();
    await screen.findByText("Lab Space");
    await expectNoA11yViolations(document.body);
  });
});
