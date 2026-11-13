import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { CollectDialog } from "./ShopOrderDialogs";

const interrupted = new StructuredApiError(409, { code: "pickup_interrupted", detail: "This order's event pickup was interrupted." });

it("explains an interrupted event pickup and offers to move it", () => {
  const move = vi.fn();
  render(<CollectDialog open onClose={() => {}} pending={false} error={interrupted} onSubmit={() => {}} onMovePickup={move} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Move this order's pickup before handing it over.");
  fireEvent.click(screen.getByRole("button", { name: "Move pickup to the makerspace" }));
  expect(move).toHaveBeenCalledTimes(1);
});

it("shows a failed move and offers nothing to a viewer who cannot move it", () => {
  const { unmount } = render(<CollectDialog open onClose={() => {}} pending={false} error={interrupted} onSubmit={() => {}}
    onMovePickup={() => {}} moveError={new StructuredApiError(403, { detail: "Not allowed." })} />);
  expect(screen.getAllByRole("alert")[1]).toHaveTextContent("Not allowed.");
  unmount();
  render(<CollectDialog open onClose={() => {}} pending={false} error={interrupted} onSubmit={() => {}} />);
  expect(screen.queryByRole("button", { name: "Move pickup to the makerspace" })).toBeNull();
});

it("offers no move for an ordinary refusal", () => {
  render(<CollectDialog open onClose={() => {}} pending={false} error={new StructuredApiError(400, { code: "pickup_code_invalid" })}
    onSubmit={() => {}} onMovePickup={() => {}} />);
  expect(screen.getByRole("alert")).toHaveTextContent("That pickup code does not match this order.");
  expect(screen.queryByRole("button", { name: "Move pickup to the makerspace" })).toBeNull();
});
