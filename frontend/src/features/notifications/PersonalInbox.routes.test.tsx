import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PersonalInbox } from "./PersonalInbox";

const { request, tenant } = vi.hoisted(() => ({ request: vi.fn(), tenant: vi.fn() }));
vi.mock("../../lib/api", () => ({ memberRequest: request, staffRequest: request, getAccessToken: () => null }));
vi.mock("../../lib/tenant", async importOriginal => ({
  ...await importOriginal<typeof import("../../lib/tenant")>(), useOptionalTenant: tenant,
}));

describe("inbox Open action", () => {
  it.each([
    ["single", true, "/m/local/member/events/4/ticket", "/member/events/4/ticket"],
    ["single", false, "/m/local/admin/reports", "/admin/reports"],
    ["central", true, "/member/bookings", "/m/local/member/bookings"],
    ["central", false, "/admin/reports", "/m/local/admin/reports"],
  ] as const)("uses %s routes for member=%s and saved %s", async (mode, member, link, expected) => {
    tenant.mockReturnValue({ mode, slug: mode === "single" ? "local" : "" });
    request.mockImplementation(async (path: string) => path.endsWith("/unread-count") ? { count: 0 } : {
      count: 1, next: null, previous: null, results: [{ id: 1, feature: "events", event: "updated", link,
        title: "Update", summary: "Details", read_at: "2026-10-11T00:01:00Z", created_at: "2026-10-11T00:00:00Z" }],
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><MemoryRouter>
      <PersonalInbox makerspaceId={7} makerspaceSlug="local" member={member} />
    </MemoryRouter></QueryClientProvider>);
    try {
      expect(await screen.findByRole("link", { name: "Open" })).toHaveAttribute("href", expected);
    } finally { view.unmount(); client.clear(); request.mockReset(); tenant.mockReset(); }
  });
});
