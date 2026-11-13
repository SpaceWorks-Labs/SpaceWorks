import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { memberRequest } from "../../lib/api";
import { MemberMachineAccess } from "./MemberMachineAccess";

vi.mock("../../lib/api", () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }));

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberMachineAccess makerspaceId={3} /></QueryClientProvider>);
}

describe("my machine access", () => {
  it("shows live and ended access plus the machines open to all members", async () => {
    vi.mocked(memberRequest).mockResolvedValue({
      grants: [
        { id: 1, machine_id: null, machine_name: null, machine_type_name: "Laser", granted_at: "2026-11-01T00:00:00Z", expires_at: null, status: "live" },
        { id: 2, machine_id: 9, machine_name: "Mill 1", machine_type_name: null, granted_at: "2026-01-01T00:00:00Z", expires_at: "2026-02-01T00:00:00Z", status: "expired" },
      ],
      open_machines: [{ id: 4, name: "Bench saw" }],
    });
    show();
    expect(await screen.findByText(/Every Laser machine/)).toBeVisible();
    expect(screen.getByText("Mill 1")).toBeVisible();
    expect(screen.getByText("Has access")).toBeVisible();
    expect(screen.getByText("Ended")).toBeVisible();
    expect(screen.getByText("Ask a space manager to renew it.", { exact: false })).toBeVisible();
    expect(screen.getByText("Bench saw")).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith("/member/makerspaces/3/machine-access");
  });

  it("explains an empty list without mentioning training", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ grants: [], open_machines: [] });
    show();
    expect(await screen.findByText(/You have not been given access to any machine yet/)).toBeVisible();
    expect(screen.queryByText(/certif|training|induction/i)).toBeNull();
  });

  it("keeps an unavailable list distinct from an empty one", async () => {
    vi.mocked(memberRequest).mockRejectedValue(new Error("Access unavailable"));
    show();
    expect(await screen.findByRole("alert")).toHaveTextContent("Access unavailable");
    expect(screen.queryByText(/You have not been given access/)).toBeNull();
  });
});
