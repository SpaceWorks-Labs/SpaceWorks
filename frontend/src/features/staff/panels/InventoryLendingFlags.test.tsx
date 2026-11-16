import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";

import { InventoryLendingFlags, type LendingFlagSpace } from "./InventoryLendingFlags";
import { emptyForm, formFromProduct, payloadFromForm, type AdminProduct, type ItemForm } from "./InventoryPanelShared";

function Harness({ space, start = emptyForm, onForm }: { space?: LendingFlagSpace; start?: ItemForm; onForm?: (form: ItemForm) => void }) {
  const [form, setForm] = useState(start);
  onForm?.(form);
  return <InventoryLendingFlags form={form} setForm={updater => setForm(current => updater(current))} makerspace={space} />;
}

const both: LendingFlagSpace = { enabled_modules: ["public_inventory"], enabled_features: ["loans.enabled", "inventory.consumables", "inventory.expected_back"] };

it("offers both switches when their capabilities are on, and sends them in the payload", () => {
  let latest = emptyForm;
  render(<Harness space={both} onForm={form => { latest = form; }} />);
  fireEvent.click(screen.getByLabelText("Consumable (logged as used, never lent)"));
  fireEvent.click(screen.getByLabelText("Show expected-back date on the public page"));
  expect(payloadFromForm(latest, false)).toMatchObject({ is_consumable: true, public_show_expected_back: true });
});

it("hides the consumable switch for individually tracked items and everything when switched off", () => {
  const { unmount } = render(<Harness space={both} start={{ ...emptyForm, tracking_mode: "individual" }} />);
  expect(screen.queryByLabelText(/Consumable/)).not.toBeInTheDocument();
  expect(screen.getByLabelText(/expected-back/)).toBeInTheDocument();
  unmount();
  render(<Harness space={{ enabled_modules: [], enabled_features: ["loans.enabled", "inventory.expected_back"] }} />);
  // inventory.expected_back needs its parent module installed.
  expect(screen.queryByText("Use and return")).not.toBeInTheDocument();
});

it("leaves the fields out of the payload until the product carries them", () => {
  expect(payloadFromForm(emptyForm, false)).not.toHaveProperty("is_consumable");
  const product = { name: "Tape", tracking_mode: "quantity", is_consumable: true, public_show_expected_back: false } as unknown as AdminProduct;
  expect(payloadFromForm(formFromProduct(product), false)).toMatchObject({ is_consumable: true, public_show_expected_back: false });
});
