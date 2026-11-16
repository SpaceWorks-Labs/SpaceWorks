import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";

import { AvailabilityBadge } from "./AvailabilityBadge";
import { ProductCard } from "./ProductCard";
import type { Product } from "../../types/inventory";

const product: Product = { id: 4, name: "Oscilloscope", description: "", event_only: true,
  availability: { mode: "status_only", label: "Lent at events only" } };

it("labels an event-only item and offers no way to add it to a request", () => {
  render(<MemoryRouter><ProductCard product={product} quantity={0} onDecrement={() => {}} onIncrement={() => {}} onOpenDetails={() => {}} /></MemoryRouter>);
  expect(screen.getAllByText("Lent at events only").length).toBeGreaterThanOrEqual(1);
  expect(screen.queryByRole("button", { name: "Add Oscilloscope" })).toBeNull();
  expect(screen.getByRole("button", { name: "Details" })).toBeInTheDocument();
});

it("keeps the request stepper for an ordinary item", () => {
  render(<MemoryRouter><ProductCard product={{ ...product, event_only: false, availability: { mode: "status_only", label: "Available" } }}
    quantity={0} onDecrement={() => {}} onIncrement={() => {}} onOpenDetails={() => {}} /></MemoryRouter>);
  expect(screen.getByRole("button", { name: "Add Oscilloscope" })).toBeEnabled();
});

it("renders the event-only availability label as a badge", () => {
  render(<AvailabilityBadge availability={{ mode: "status_only", label: "Lent at events only" }} />);
  expect(screen.getByText("Lent at events only")).toBeInTheDocument();
});

it("reads as not borrowable, with no event wording, while Events is off (decision 228a)", () => {
  render(<MemoryRouter><ProductCard product={product} eventsOn={false} quantity={0} onDecrement={() => {}} onIncrement={() => {}} onOpenDetails={() => {}} /></MemoryRouter>);
  expect(screen.getByText("Not available to borrow right now")).toBeInTheDocument();
  expect(screen.getByText("Unavailable")).toBeInTheDocument();
  expect(screen.queryByText("Lent at events only")).toBeNull();
  expect(screen.queryByRole("button", { name: "Add Oscilloscope" })).toBeNull();
});
