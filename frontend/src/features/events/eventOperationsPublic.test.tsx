import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { publicV1Request } from "../../lib/api";
import { EventDiscoverPage, organizerOptions } from "./EventDiscoverPage";
import { EventVenueDetails, venueMapHref } from "./EventVenueDetails";
import { PayByNotice } from "./PayByNotice";
vi.mock("../../lib/api", async importOriginal => ({ ...await importOriginal<typeof import("../../lib/api")>(), publicV1Request: vi.fn() }));
afterEach(() => { window.history.replaceState(null, "", "/"); vi.mocked(publicV1Request).mockReset(); });

describe("venue details (E-B7 venue fields)", () => {
  it("prefers the organiser's map link and falls back to an address search", () => {
    expect(venueMapHref({ venue_address: "1 Main St", venue_map_url: "https://maps.example/x" })).toBe("https://maps.example/x");
    expect(venueMapHref({ location: "Hall B", venue_address: "1 Main St" })).toBe("https://www.google.com/maps/search/?api=1&query=Hall%20B%2C%201%20Main%20St");
    expect(venueMapHref({ location: "Hall B" })).toBeNull();
  });
  it("renders nothing without venue details and a directions link with them", () => {
    const { container, rerender } = render(<EventVenueDetails venue={{ location: "Hall B" }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<EventVenueDetails venue={{ location: "Hall B", venue_address: "1 Main St" }} />);
    expect(screen.getByRole("link", { name: /Get directions/ })).toHaveAttribute("target", "_blank");
  });
});

describe("pay window (E-B5)", () => {
  it("tells the guest when to pay and staff the deadline", () => {
    const future = new Date(Date.now() + 3_600_000).toISOString();
    const { rerender } = render(<PayByNotice payBy={future} audience="guest" />);
    expect(screen.getByText(/^Pay by .* to keep your place\.$/)).toBeInTheDocument();
    rerender(<PayByNotice payBy={future} audience="staff" />);
    expect(screen.getByText(/^Pay by /)).toBeInTheDocument();
    rerender(<PayByNotice payBy={null} audience="staff" />);
    expect(screen.queryByText(/Pay by/)).not.toBeInTheDocument();
  });
});

describe("discover filters (A14)", () => {
  it("applies tag and organiser from the link and shows them as removable chips", async () => {
    window.history.replaceState(null, "", "/discover/events?tag=robotics&organization=makers-guild");
    vi.mocked(publicV1Request).mockImplementation(async path => String(path).startsWith("/discover/events/organizers/")
      ? { next: null, results: [{ slug: "makers-guild", name: "Makers Guild" }, { slug: "gear-club", name: "Gear Club" }] }
      : { count: 0, next: null, previous: null, results: [] });
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><EventDiscoverPage /></MemoryRouter></QueryClientProvider>);
    const listCalls = () => vi.mocked(publicV1Request).mock.calls.map(([path]) => String(path)).filter(path => path.startsWith("/discover/events/?"));
    await waitFor(() => expect(listCalls().length).toBeGreaterThan(0));
    expect(listCalls()[0]).toContain("tag=robotics");
    expect(listCalls()[0]).toContain("organization=makers-guild");
    expect(await screen.findByRole("button", { name: /Organiser: Makers Guild/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Gear Club" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Tag: robotics/ }));
    await waitFor(() => expect(listCalls().at(-1)).not.toContain("tag="));
  });
  it("keeps a linked organiser selectable even when it no longer appears in the list", () => {
    expect(organizerOptions([{ slug: "a", name: "A" }], "gone")).toEqual([{ slug: "a", name: "A" }, { slug: "gone", name: "gone" }]);
    expect(organizerOptions([{ slug: "a", name: "A" }], "a")).toHaveLength(1);
  });
});
