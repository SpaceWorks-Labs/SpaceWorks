import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditLog } from "./AuditLog";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api")), staffRequest }));

const page = { count: 1, next: null, previous: null, results: [{ id: 8, action: "space_control.announcement_created",
  action_label: "Announcement created", actor_display: "Root", target_type: "space_controls.platformannouncement", target_id: "3",
  meta: {}, meta_redacted: false, created_at: "2026-11-01T10:00:00Z" }] };

describe("Platform audit log (#190)", () => {
  beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue(page); });

  it("searches every space through the platform context and can narrow to platform-level rows", async () => {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter><AuditLog platform /></MemoryRouter></QueryClientProvider>);
    expect(await screen.findByText("Announcement created")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Platform audit log" })).toBeInTheDocument();
    const first = staffRequest.mock.calls[0];
    expect(first[0]).toMatch(/^\/admin\/audit-logs\?/);
    expect(first[0]).not.toContain("makerspace=");
    expect(first[2]).toBe("platform");
    fireEvent.click(await screen.findByLabelText("Platform-level rows only", undefined, { timeout: 100 }).catch(async () => {
      fireEvent.click(screen.getByRole("button", { name: /filter/i }));
      return screen.findByLabelText("Platform-level rows only");
    }));
    await waitFor(() => expect(staffRequest.mock.calls.some(call => String(call[0]).includes("platform_only=true"))).toBe(true));
  });
});
