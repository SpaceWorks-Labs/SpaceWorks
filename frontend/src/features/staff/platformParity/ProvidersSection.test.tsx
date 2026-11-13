import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { ProvidersSection } from "./ProvidersSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);
const never = { at: null, by: null };
const sms = { provider: "sms", values: { is_enabled: false, provider: "twilio", account_sid: "AC1", from_number: "+447700900123",
  notifications_enabled: false, notifications_from_number: "" },
  secrets: [{ name: "auth_token", set: true, last_changed: { at: "2026-11-01T10:00:00Z", by: "root" } }],
  info: {}, updated_at: "2026-11-01T10:00:00Z", last_changed: { at: "2026-11-01T10:00:00Z", by: "root" }, test: "send" };
const whatsapp = { provider: "whatsapp", values: { is_enabled: false, app_id: "", phone_number_id: "", business_account_id: "" },
  secrets: [{ name: "access_token", set: false, last_changed: never }, { name: "app_secret", set: false, last_changed: never }],
  info: { webhook_verify_token: "verify-me", callback_url: "https://example.test/hook" }, updated_at: null, last_changed: never, test: "check" };

function renderSection() {
  request.mockImplementation(async (path, init) => {
    if (path === "/admin/platform/sms-settings/test") return { outcome: "sent" } as never;
    if (path === "/admin/platform/sms-settings") return (init?.method === "PATCH" ? sms : sms) as never;
    if (path === "/admin/platform/whatsapp-settings") return whatsapp as never;
    throw new Error(path);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><ProvidersSection /></QueryClientProvider>);
}

describe("ProvidersSection", () => {
  beforeEach(() => { request.mockReset(); });

  it("shows a saved secret only as set, and sends only what changed", async () => {
    renderSection();
    expect(await screen.findByText("Set")).toBeInTheDocument();
    const token = screen.getByLabelText("Auth token");
    expect(token).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Account SID"), { target: { value: "AC2" } });
    fireEvent.change(token, { target: { value: "new-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/sms-settings", { method: "PATCH",
      body: JSON.stringify({ account_sid: "AC2", auth_token: "new-token" }) }, "platform"));
  });

  it("sends a test text to the typed number", async () => {
    renderSection();
    fireEvent.change(await screen.findByLabelText("Send a test text to"), { target: { value: "+447700900111" } });
    fireEvent.click(screen.getByRole("button", { name: "Send test" }));
    expect(await screen.findByText("Test message sent. Check the phone.")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/platform/sms-settings/test", { method: "POST", body: JSON.stringify({ to: "+447700900111" }) }, "platform");
  });

  it("shows the WhatsApp webhook facts and a credential check", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("radio", { name: "WhatsApp" }));
    expect(await screen.findByText("verify-me")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check credentials" })).toBeInTheDocument();
    expect(screen.getAllByText("Not set")).toHaveLength(2);
  });
});
