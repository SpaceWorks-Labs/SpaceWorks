import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InventoryItemFields } from "./InventoryItemFields";
import { emptyForm } from "./InventoryPanelShared";
describe("public inventory visibility preview", () => {
 it.each([
  [{ is_public: false }, "Not in the public catalogue"],
  [{ public_availability_mode: "hidden" }, "Availability hidden"],
  [{ public_availability_mode: "exact_count", show_public_count: false }, "Limited"],
  [{ public_availability_mode: "exact_count", show_public_count: true }, "2 available"],
  [{ available_quantity: "0" }, "Unavailable"],
 ])("respects the public display gates: %s", (patch, label) => {
  render(<InventoryItemFields form={{ ...emptyForm, total_quantity: "20", available_quantity: "2", ...patch }} setForm={() => {}} categories={[]} />);
  expect(screen.getByText(label)).toBeInTheDocument();
 });
});
