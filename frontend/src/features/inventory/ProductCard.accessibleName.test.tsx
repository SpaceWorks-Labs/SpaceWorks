import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import type { Product } from "../../types/inventory";
import { ProductCard } from "./ProductCard";

it.each([null, "/drill.jpg"])("includes the visible availability badge in the details action name (image %s)", image => {
  const onOpenDetails = vi.fn();
  const product = { id: 7, name: "Drill", description: "", image_url: image,
    availability: { mode: "exact_count", count: 4, label: "Available" } } as Product;
  render(<MemoryRouter><ProductCard product={product} quantity={0} onIncrement={vi.fn()}
    onDecrement={vi.fn()} onOpenDetails={onOpenDetails} /></MemoryRouter>);
  const details = screen.getByRole("button", { name: "Open details for Drill 4 available" });
  expect(details).toHaveTextContent("4 available");
  details.click();
  expect(onOpenDetails).toHaveBeenCalledOnce();
});
