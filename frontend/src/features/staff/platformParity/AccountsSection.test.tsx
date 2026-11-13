import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { AccountsSection } from "./AccountsSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const account = { id: 7, username: "ada", account_kind: "member", is_active: true, access_status: "active", mfa_enabled: true, staff_role_count: 2 };

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><AccountsSection /></QueryClientProvider>);
}

describe("AccountsSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (_path, init) => (init?.method === "POST" ? account : [account]) as never);
  });

  it("looks an account up by exact user name and shows its state without personal details", async () => {
    renderSection();
    fireEvent.change(screen.getByRole("textbox", { name: "User name" }), { target: { value: " ada " } });
    fireEvent.click(screen.getByRole("button", { name: "Find account" }));
    expect(await screen.findByText("ada")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/platform/accounts?username=ada", {}, "platform");
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("Two-step on")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Re-enable…" })).not.toBeInTheDocument();
  });

  it("asks for a reason before disabling", async () => {
    renderSection();
    fireEvent.change(screen.getByRole("textbox", { name: "User name" }), { target: { value: "ada" } });
    fireEvent.click(screen.getByRole("button", { name: "Find account" }));
    fireEvent.click(await screen.findByRole("button", { name: "Disable…" }));
    const confirm = screen.getByRole("button", { name: "Disable account" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: "Reason" }), { target: { value: "Stolen laptop" } });
    fireEvent.click(confirm);
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/accounts/7/disable",
      { method: "POST", body: JSON.stringify({ reason: "Stolen laptop" }) }, "platform"));
  });
});
