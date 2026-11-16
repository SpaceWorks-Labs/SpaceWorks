import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { StructuredApiError } from "../../../lib/api/errors";
import { IpAccessSection } from "./IpAccessSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);

const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const rule = { id: 1, cidr: "198.51.100.0/24", action: "deny", note: "scanner", expires_at: null, active: true, created_by: "root", created_at: "2026-11-01T10:00:00Z" };
const block = { id: 4, network: "203.0.113.9/32", blocked_until: "2099-01-01T00:00:00Z", created_at: "2026-11-05T09:00:00Z", active: true };

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><IpAccessSection /></QueryClientProvider>);
}

describe("IpAccessSection", () => {
  beforeEach(() => {
    request.mockReset();
    request.mockImplementation(async (path, init) => {
      if (init?.method === "POST" && path === "/admin/platform/ip-rules") throw new StructuredApiError(400, { cidr: ["This rule would lock you out."] });
      if (init?.method === "POST") return { unblocked: 1 } as never;
      return (path.startsWith("/admin/platform/ip-blocks") ? page([block]) : page([rule])) as never;
    });
  });

  it("keeps the visible lift action in its accessible name and names the network", async () => {
    renderSection();
    const lift = await screen.findByText("Lift now…", { selector: "button", exact: true });
    expect(lift).toHaveAccessibleName(/^Lift now… 203\.0\.113\.9\/32$/);
  });

  it("lists rules and active automatic blocks", async () => {
    renderSection();
    expect(await screen.findByText("198.51.100.0/24")).toBeInTheDocument();
    expect(screen.getByText("Deny")).toBeInTheDocument();
    expect(await screen.findByText("203.0.113.9/32", { selector: ".title-section" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Lift now… 203.0.113.9/32" }));
    fireEvent.click(screen.getByRole("button", { name: "Lift block" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/ip-blocks/4/unblock", { method: "POST", body: "{}" }, "platform"));
  });

  it("shows a lock-out refusal under the address field", async () => {
    renderSection();
    fireEvent.click(screen.getByRole("button", { name: "New rule" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Address or range" }), { target: { value: "0.0.0.0/0" } });
    fireEvent.click(screen.getByRole("button", { name: "Add rule" }));
    expect(await screen.findByText("This rule would lock you out.")).toBeInTheDocument();
  });
});
