import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { MachineAccessPanel } from "./MachineAccessPanel";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));

const grant = { id: 5, member: 11, member_name: "Asha", machine: null, machine_name: null, machine_type: 3, machine_type_name: "Laser",
  granted_by_name: "Boss", granted_at: "2026-11-01T00:00:00Z", expires_at: null, note: "Passed the walkthrough", source: "staff", revoked_at: null, status: "live" };
const targets = { types: [{ id: 3, name: "Laser" }], machines: [{ id: 8, name: "Laser 1", machine_type: 3 }] };

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MachineAccessPanel makerspaceId={2} targets={targets} /></QueryClientProvider>);
}

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe("machine access (decision 319)", () => {
  it("lists who has access, to what, and the note", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 1, next: null, previous: null, results: [grant] });
    show();
    expect(await screen.findByText("Asha")).toBeVisible();
    expect(screen.getAllByText("Has access").length).toBeGreaterThan(0);
    expect(screen.getByText("Passed the walkthrough")).toBeVisible();
    expect(screen.getByText(/Every Laser machine/)).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/2/machine-access?status=live&page=1");
  });

  it("lists only grants converted from certifications for review (decision 335a)", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 1, next: null, previous: null, results: [{ ...grant, source: "migration" }] });
    show();
    expect(await screen.findByText("Carried over")).toBeVisible();
    fireEvent.click(screen.getByRole("checkbox", { name: /carried over at the upgrade/ }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/2/machine-access?status=live&page=1&source=migration"));
  });

  it("shows an honest empty state and no certification wording", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    show();
    expect(await screen.findByText(/No one has machine access here yet/)).toBeVisible();
    expect(screen.queryByText(/certif/i)).toBeNull();
  });

  it("revokes after confirmation and refreshes the list", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: { method?: string }) => path.includes("/revoke") && options?.method === "POST"
      ? { ...grant, status: "revoked" } : { count: 1, next: null, previous: null, results: [grant] });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Revoke access" }));
    fireEvent.click(await screen.findByRole("button", { name: "Revoke" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/machine-access/5/revoke", { method: "POST" }));
  });

  it("gives access to a found member for a chosen type, with a note", async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: { method?: string }) => {
      if (options?.method === "POST") return { granted: [grant], failed: [] };
      if (path.includes("/candidates")) return { results: [{ user_id: 11, name: "Asha" }] };
      return { count: 0, next: null, previous: null, results: [] };
    });
    show();
    await screen.findByText(/No one has machine access here yet/);
    fireEvent.change(screen.getByLabelText("Machine or machine type"), { target: { value: "type:3" } });
    fireEvent.change(screen.getByLabelText("Find members"), { target: { value: "ash" } });
    fireEvent.click(await screen.findByRole("button", { name: "Add Asha" }));
    fireEvent.change(screen.getByLabelText("Note (optional)"), { target: { value: "ok" } });
    fireEvent.click(screen.getByRole("button", { name: "Give access" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/2/machine-access", {
      method: "POST", body: JSON.stringify({ member_ids: [11], expires_at: null, note: "ok", machine_type_id: 3 }),
    }));
  });
});
