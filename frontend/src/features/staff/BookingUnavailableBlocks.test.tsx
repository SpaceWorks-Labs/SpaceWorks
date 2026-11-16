import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const staffRequest = vi.fn();
vi.mock("../../lib/api", () => ({ staffRequest: (...args: unknown[]) => staffRequest(...args) }));

import { BookingUnavailableBlocks } from "./BookingUnavailableBlocks";

function renderBlocks() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><BookingUnavailableBlocks spaceId={7} /></QueryClientProvider>);
}

describe("BookingUnavailableBlocks", () => {
  it("shows outages and repairs with staff detail, never the nightly closures", async () => {
    staffRequest.mockResolvedValue({ timezone: "UTC", unavailable: [
      { starts_at: "2026-11-12T00:00:00Z", ends_at: "2026-11-12T09:00:00Z", kind: "closed", severity: "block", reason: "" },
      { starts_at: "2026-11-12T09:00:00Z", ends_at: "2026-11-13T09:00:00Z", kind: "room_outage", severity: "warn", reason: "Leaky roof" },
      { starts_at: "2026-11-14T09:00:00Z", ends_at: "2026-11-14T12:00:00Z", kind: "machine_repair", severity: "block", reason: "" },
    ] });
    renderBlocks();
    expect(await screen.findByText("Room out of service (bookings still allowed)")).toBeInTheDocument();
    expect(screen.getByText("Leaky roof")).toBeInTheDocument();
    expect(screen.getByText("Machine under repair")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(staffRequest.mock.calls[0][0]).toMatch(/^\/admin\/spaces\/7\/bookings\/availability\/\?starts_at=/);
  });

  it("renders nothing when the room is free or the read fails", async () => {
    staffRequest.mockRejectedValue(new Error("403"));
    const { container } = renderBlocks();
    await vi.waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});
