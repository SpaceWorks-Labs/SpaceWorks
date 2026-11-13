import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import type { Makerspace } from "../../../types/inventory";
import { SpaceCard } from "./SpaceCard";

const base: Makerspace = { name: "Alpha Robotics Lab", public_code: "RQBG", slug: "alpha-lab", location: "Main Campus" };
const mount = (space: Makerspace) => render(<MemoryRouter><SpaceCard space={space} /></MemoryRouter>);

describe("SpaceCard (decision 275 change)", () => {
  it("leads with the space's own cover image and falls back to the brand colour field only without one", () => {
    const { container, unmount } = mount({ ...base, cover_image_url: "/cover.jpg", logo_url: "/logo.png" });
    const field = container.querySelector(".sw-space-field")!;
    expect(field.querySelector("img")).toHaveAttribute("src", "/cover.jpg");
    expect(field).not.toHaveAttribute("data-tile");
    expect(container.querySelector(".sw-space-mark img")).toHaveAttribute("src", "/logo.png");
    unmount();
    const fallback = mount(base).container.querySelector(".sw-space-field")!;
    expect(fallback).toHaveAttribute("data-tile");
    expect(fallback).toHaveTextContent("RQBG");
  });

  it("lists what the space offers as translated chips in the server's order and skips unknown keys", () => {
    mount({ ...base, offers: ["inventory", "machines", "events", "bookings", "shop", "memberships", "donations", "rockets" as never] });
    const list = screen.getByRole("list", { name: "What this space offers" });
    expect(within(list).getAllByRole("listitem").map(item => item.textContent)).toEqual(
      ["Tool loans", "Machines", "Events", "Room bookings", "Shop", "Memberships", "Donations"]);
    expect(list.querySelectorAll("svg")).toHaveLength(7);
  });

  it("shows no offers list when the space offers nothing public", () => {
    mount({ ...base, offers: [] });
    expect(screen.queryByRole("list", { name: "What this space offers" })).toBeNull();
  });

  it("links the next public event on its own, above the whole-card link", () => {
    mount({ ...base, next_event: { title: "Intro to laser cutting", starts_at: "2026-11-20T18:00:00Z", public_url: "/m/alpha-lab/events/abc123" } });
    expect(screen.getByRole("link", { name: "Intro to laser cutting" })).toHaveAttribute("href", "/m/alpha-lab/events/abc123");
    expect(screen.getByRole("link", { name: "Alpha Robotics Lab" })).toHaveAttribute("href", "/m/alpha-lab");
    expect(screen.getByText(/Next event/)).toBeInTheDocument();
    expect(document.querySelector("time")).toHaveAttribute("dateTime", "2026-11-20T18:00:00Z");
  });

  it("ignores a missing or non-relative next event", () => {
    mount({ ...base, next_event: { title: "Elsewhere", starts_at: "2026-11-20T18:00:00Z", public_url: "https://evil.example/x" } });
    expect(screen.queryByRole("link", { name: "Elsewhere" })).toBeNull();
    expect(screen.queryByText(/Next event/)).toBeNull();
  });

  it("has no axe violations with offers and an event", async () => {
    const { container } = mount({ ...base, cover_image_url: "/c.jpg", offers: ["inventory", "events"],
      next_event: { title: "Open night", starts_at: "2026-11-20T18:00:00Z", public_url: "/m/alpha-lab/events/x" } });
    await expectNoA11yViolations(container);
  });
});
