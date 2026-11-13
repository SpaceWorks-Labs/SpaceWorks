import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<object>(), staffRequest }));

import { SpaceEmailSender } from "./SpaceEmailSender";

const space = { email_from_name: "", email_reply_to: "", smtp_verified: false, smtp_verified_at: null, enabled_features: ["email.sender_identity"] };
const wrap = (ui: import("react").ReactElement) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>;

beforeEach(() => { staffRequest.mockReset(); });

describe("space email sender and SMTP test (parity A19)", () => {
  it("sends a test email and shows the verified state", async () => {
    let verified = false;
    staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.endsWith("/email/test")) { verified = true; return { accepted: true, code: "provider_accepted", smtp_verified: true, smtp_verified_at: "2026-11-11T09:00:00Z" }; }
      return { ...space, smtp_verified: verified, smtp_verified_at: verified ? "2026-11-11T09:00:00Z" : null, ...(options?.method === "PATCH" ? JSON.parse(String(options.body)) : {}) };
    });
    render(wrap(<SpaceEmailSender makerspaceId={4} />));
    expect(await screen.findByText("Not verified")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Send a test email" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/4/email/test", { method: "POST" }));
    expect(await screen.findByText(/Test email accepted/)).toBeVisible();
    expect(await screen.findByText("Verified")).toBeVisible();
  });

  it("explains a refused test (422) in plain words", async () => {
    staffRequest.mockImplementation(async (path: string) => {
      if (path.endsWith("/email/test")) throw new StructuredApiError(422, { accepted: false, code: "smtp_probe_failed", smtp_verified: false, smtp_verified_at: null } as never);
      return space;
    });
    render(wrap(<SpaceEmailSender makerspaceId={4} />));
    fireEvent.click(await screen.findByRole("button", { name: "Send a test email" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not be reached or refused the sign-in/);
  });

  it("saves the sender name and reply-to, and hides them when the switch is off", async () => {
    staffRequest.mockImplementation(async (_path: string, options?: RequestInit) => ({ ...space, ...(options?.method === "PATCH" ? JSON.parse(String(options.body)) : {}) }));
    const view = render(wrap(<SpaceEmailSender makerspaceId={4} />));
    fireEvent.change(await screen.findByLabelText("Sender name"), { target: { value: " North Lab " } });
    fireEvent.change(screen.getByLabelText("Reply-to address"), { target: { value: "desk@north.example" } });
    fireEvent.click(screen.getByRole("button", { name: "Save sender details" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/4", { method: "PATCH",
      body: JSON.stringify({ email_from_name: "North Lab", email_reply_to: "desk@north.example" }) }));
    view.unmount();
    staffRequest.mockResolvedValue({ ...space, enabled_features: [] });
    render(wrap(<SpaceEmailSender makerspaceId={4} />));
    expect(await screen.findByRole("button", { name: "Send a test email" })).toBeVisible();
    expect(screen.queryByLabelText("Sender name")).toBeNull();
  });
});
