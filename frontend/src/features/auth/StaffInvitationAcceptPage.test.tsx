import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api/errors";
import { StaffInvitationAcceptPage } from "./StaffInvitationAcceptPage";

const api = vi.hoisted(() => ({ memberRequest: vi.fn(), refreshAccessToken: vi.fn(), logout: vi.fn() }));
vi.mock("../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), ...api }));
vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Person sign-in</p> }));
const mount = () => render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><StaffInvitationAcceptPage /></MemoryRouter></QueryClientProvider>);

describe("staff invitation acceptance (signed in + fresh email code)", () => {
  beforeEach(() => {
    Object.values(api).forEach(fn => fn.mockReset());
    window.history.replaceState(null, "", "/staff-invitations/accept#token=private-token-1234567890&space=the-lab");
  });

  it("asks a signed-out visitor to sign in first", async () => {
    api.refreshAccessToken.mockResolvedValue(false);
    mount();
    expect(await screen.findByText("Person sign-in")).toBeInTheDocument();
    expect(api.memberRequest).not.toHaveBeenCalled();
  });

  it("emails a code, then accepts with it and clears the bearer from the URL", async () => {
    api.refreshAccessToken.mockResolvedValue(true);
    api.memberRequest.mockResolvedValueOnce({ challenge_required: true, detail: "Sent." })
      .mockResolvedValueOnce({ challenge_required: false, detail: "You now have a staff role at The Lab.", makerspace: { id: 1, slug: "the-lab", name: "The Lab" } });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Email me a code" }));
    fireEvent.change(await screen.findByLabelText("6-digit code"), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    expect(await screen.findByRole("status")).toHaveTextContent("You now have a staff role at The Lab.");
    expect(JSON.parse(api.memberRequest.mock.calls[1][1].body)).toEqual({ token: "private-token-1234567890", makerspace_slug: "the-lab", code: "123456" });
    expect(window.location.hash).toBe("");
    expect(screen.getByRole("link", { name: "Open the staff console" })).toHaveAttribute("href", "/m/the-lab/admin");
    expect(document.body.textContent).not.toMatch(/password/i);
  });

  it("explains an email mismatch and offers another account", async () => {
    api.refreshAccessToken.mockResolvedValue(true);
    api.memberRequest.mockRejectedValue(new StructuredApiError(403, { code: "invite_email_mismatch", detail: "x" }));
    mount();
    fireEvent.click(await screen.findByRole("button", { name: "Email me a code" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("different email address");
    await waitFor(() => expect(screen.getByRole("button", { name: "Sign out and use another account" })).toBeInTheDocument());
  });
});
