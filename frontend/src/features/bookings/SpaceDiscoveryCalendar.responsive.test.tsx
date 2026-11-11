import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SpaceDiscoveryCalendar } from "./SpaceDiscoveryCalendar";
import { usePublicAvailability, type PublicBookableSpace } from "./publicBookingsApi";

vi.mock("./publicBookingsApi", () => ({ usePublicAvailability: vi.fn() }));
const space = { public_token: "bench", name: "Bench", show_public_availability: true, show_public_booker_names: false } as PublicBookableSpace;
function viewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: width >= Number(query.match(/min-width: (\d+)px/)?.[1] ?? Infinity),
    addEventListener: vi.fn(), removeEventListener: vi.fn() }));
}
beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(Date.parse("2026-10-01T00:00:00Z"));
  vi.mocked(usePublicAvailability).mockReturnValue({ data: { availability: [
    { starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z", booker_name: null },
    { starts_at: "2026-10-16T09:00:00Z", ends_at: "2026-10-16T10:00:00Z", booker_name: null },
  ] }, isLoading: false, error: null } as ReturnType<typeof usePublicAvailability>);
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it.each([320, 390, 430])("lists published bookings by day instead of a seven-column grid at %ipx", width => {
  viewport(width);
  render(<SpaceDiscoveryCalendar slug="lab" space={space} month="2026-10" timeZone="UTC" />);
  expect(screen.queryByRole("table")).toBeNull();
  const agenda = screen.getByRole("region", { name: "Bench published bookings" });
  const items = agenda.querySelectorAll("li");
  expect(items).toHaveLength(2);
  // Soonest first, whatever order the API returned.
  expect(items[0].textContent).toMatch(/^Booked 09/);
});

it.each([768, 1280])("keeps the month grid at %ipx", width => {
  viewport(width);
  render(<SpaceDiscoveryCalendar slug="lab" space={space} month="2026-10" timeZone="UTC" />);
  expect(screen.getByRole("table")).toBeInTheDocument();
});
