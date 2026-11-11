import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PiiAccessBanner } from "./PiiAccessBanner";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api/requests", () => ({ staffRequest }));

const grant = { id: "g1", scope: "space", reason: "Checking a disputed loan", opened_by: "root",
  opened_at: "2026-10-26T10:00:00Z", expires_at: "2026-10-26T10:30:00Z", closed_at: null, close_reason: "", is_own: true };
const status = (overrides: Record<string, unknown>) => ({ makerspace_id: 7, viewer_is_superadmin: true, pii_visible: false,
  active: null, space_grants: [], recent: [], ...overrides });

function renderBanner() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <PiiAccessBanner makerspaceId={7} />
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("PiiAccessBanner", () => {
  it("asks a superadmin for a reason before opening a window", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(
      init?.method === "POST" ? status({ pii_visible: true, active: grant, space_grants: [grant] }) : status({})));
    renderBanner();
    expect(await screen.findByText("Personal data in this space is masked for you.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Open PII access/ }));
    const open = screen.getByRole("button", { name: "Open for 30 minutes" });
    expect(open).toBeDisabled();
    fireEvent.change(screen.getByRole("textbox", { name: /Reason/ }), { target: { value: "Checking a disputed loan" } });
    fireEvent.click(open);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/pii-access",
      { method: "POST", body: JSON.stringify({ reason: "Checking a disputed loan" }) }));
    expect(await screen.findByText(/Personal data is visible to you until/)).toBeInTheDocument();
  });

  it("lets the superadmin close an open window", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(
      init?.method === "DELETE" ? status({}) : status({ pii_visible: true, active: grant, space_grants: [grant] })));
    renderBanner();
    fireEvent.click(await screen.findByRole("button", { name: /Close now/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/pii-access", { method: "DELETE" }));
  });

  it("shows the Space Manager every open platform window, read-only", async () => {
    staffRequest.mockResolvedValue(status({ viewer_is_superadmin: false, pii_visible: true,
      space_grants: [{ ...grant, is_own: false }], recent: [{ ...grant, is_own: false }] }));
    renderBanner();
    expect(await screen.findByText("A platform administrator can see personal data in this space right now.")).toBeInTheDocument();
    expect(screen.getAllByText(/Checking a disputed loan/).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Open PII access/ })).not.toBeInTheDocument();
  });
});
