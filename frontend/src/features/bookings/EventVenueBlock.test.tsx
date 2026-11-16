import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { EventVenueBlock } from "./EventVenueBlock";

const host = { name: "North Lab", slug: "north", location: "12 Maker Street", map_url: "https://maps.google.com/?q=north", logo_url: "" };

describe("EventVenueBlock", () => {
  it("names the matched space and host, links the space and shows its photos", () => {
    render(<MemoryRouter><EventVenueBlock spaceHref={token => `/m/north/bookings/${token}`} venue={{ host,
      space: { public_token: "abc", name: "Main Hall", kind: "meeting", location: "Ground floor", capacity: 40 },
      photos: [{ id: 1, url: "https://img.test/1.webp", caption: "Hall" }] }} /></MemoryRouter>);
    expect(screen.getByText("Hosted at")).toBeInTheDocument();
    expect(screen.getByText("Main Hall, North Lab")).toBeInTheDocument();
    expect(screen.getByText("Ground floor")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "About this space" })).toHaveAttribute("href", "/m/north/bookings/abc");
    expect(screen.getByRole("region", { name: "Photos of Main Hall, North Lab" })).toBeInTheDocument();
  });

  it("falls back to the host makerspace when no public space matches", () => {
    render(<MemoryRouter><EventVenueBlock venue={{ host, space: null, photos: [] }} /></MemoryRouter>);
    expect(screen.getByText("North Lab")).toBeInTheDocument();
    expect(screen.getByText("12 Maker Street")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open map" })).toHaveAttribute("href", host.map_url);
    expect(screen.queryByRole("region")).not.toBeInTheDocument();
  });
});
