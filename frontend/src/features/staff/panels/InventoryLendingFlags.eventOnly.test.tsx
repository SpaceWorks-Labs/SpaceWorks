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

it("offers Lend only at events while the events module runs and sends it", () => {
  let latest = emptyForm;
  render(<Harness space={{ enabled_modules: ["events"], enabled_features: [] }} onForm={form => { latest = form; }} />);
  fireEvent.click(screen.getByRole("checkbox", { name: /Lend only at events/ }));
  expect(payloadFromForm(latest, false)).toMatchObject({ event_only: true });
});

it("hides it with events off or for a consumable, and round-trips the stored flag", () => {
  const { unmount } = render(<Harness space={{ enabled_modules: [], enabled_features: [] }} />);
  expect(screen.queryByText(/Lend only at events/)).toBeNull();
  unmount();
  render(<Harness space={{ enabled_modules: ["events"], enabled_features: [] }} start={{ ...emptyForm, is_consumable: true }} />);
  expect(screen.queryByText(/Lend only at events/)).toBeNull();
  const product = { name: "Scope", tracking_mode: "quantity", event_only: true } as unknown as AdminProduct;
  expect(payloadFromForm(formFromProduct(product), false)).toMatchObject({ event_only: true });
  expect(payloadFromForm(emptyForm, false)).not.toHaveProperty("event_only");
});
