import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ProductQuickViewModal } from "./ProductQuickViewModal";
import type { Product } from "../../types/inventory";

it("presents public quick view in the shared detail drawer and closes it", () => {
  const close = vi.fn();
  const product = { id: 7, name: "Drill", description: "For woodwork", tracking_mode: "individual", availability: null, image_url: null, category_name: "Tools" } as Product;
  const view = render(<ProductQuickViewModal product={product} open onClose={close} />);
  expect(screen.getByRole("dialog")).toHaveAccessibleName("Drill");
  expect(screen.getByRole("heading", { name: "Description" })).toBeVisible();
  expect(screen.getByText("For woodwork")).toBeVisible();
  expect(screen.queryByText(/Available|Unavailable|Limited/)).toBeNull();
  fireEvent.click(screen.getAllByRole("button", { name: "Close" })[0]);
  expect(close).toHaveBeenCalledOnce();
  view.rerender(<ProductQuickViewModal product={product} open={false} onClose={close} />);
  expect(screen.queryByRole("dialog")).toBeNull();
});
