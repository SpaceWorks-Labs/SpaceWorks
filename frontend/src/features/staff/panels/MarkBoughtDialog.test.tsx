import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { MarkBoughtDialog, markBoughtError } from "./MarkBoughtDialog";
import type { ToBuyItem } from "./ProcurementPanelRows";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest: request }));

const item = { id: 5, name: "PLA spool", quantity: 2, status: "ordered", vendor: null, vendor_name: "", source_consumable: null } as unknown as ToBuyItem;

beforeEach(() => {
  request.mockReset();
  request.mockImplementation(async (path: string) => path.endsWith("/vendors") ? [{ id: 3, name: "Robu" }] : { ...item, status: "received" });
});

function setup(props: Partial<{ item: ToBuyItem; vendorsEnabled: boolean }> = {}) {
  const onDone = vi.fn();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <MarkBoughtDialog item={props.item ?? item} makerspaceId={7} vendorsEnabled={props.vendorsEnabled ?? false} onClose={vi.fn()} onDone={onDone} />
  </QueryClientProvider>);
  return onDone;
}

it("records the amount, method and free-text supplier, leaving currency to the server", async () => {
  const onDone = setup();
  fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "12.50" } });
  fireEvent.change(screen.getByLabelText("Paid by"), { target: { value: "upi" } });
  fireEvent.change(screen.getByLabelText("Supplier"), { target: { value: "Local shop" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark bought" }));
  await waitFor(() => expect(onDone).toHaveBeenCalled());
  const [path, init] = request.mock.calls.find(([url]) => String(url).includes("mark-bought"))!;
  expect(path).toBe("/procurement/to-buy/5/mark-bought");
  const body = JSON.parse(init.body);
  expect(body).toMatchObject({ amount: "12.50", method: "upi", vendor_name: "Local shop" });
  expect(body).not.toHaveProperty("currency");
  expect(body).not.toHaveProperty("refill_amount");
});

it("asks for grams received when the row came from a machine consumable", async () => {
  setup({ item: { ...item, source_consumable: 11 } });
  fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "900" } });
  const submit = screen.getByRole("button", { name: "Mark bought" });
  expect(submit).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/Amount received \(grams\)/), { target: { value: "1000" } });
  fireEvent.click(submit);
  await waitFor(() => expect(request).toHaveBeenCalledWith("/procurement/to-buy/5/mark-bought", expect.objectContaining({ body: expect.stringContaining('"refill_amount":"1000"') })));
});

it("sends the saved vendor id when the vendor picker is on", async () => {
  setup({ vendorsEnabled: true });
  await screen.findByRole("option", { name: "Robu" });
  fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText("Supplier"), { target: { value: "3" } });
  expect(screen.queryByLabelText("Supplier name")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mark bought" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/procurement/to-buy/5/mark-bought", expect.objectContaining({ body: expect.stringContaining('"vendor_id":3') })));
});

it("explains 409 ledger codes and a 403 in plain words", async () => {
  request.mockImplementation(async () => { throw new StructuredApiError(409, { detail: "Already recorded.", code: "ledger_source_conflict" }); });
  setup();
  fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "5" } });
  fireEvent.click(screen.getByRole("button", { name: "Mark bought" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("already in the finance ledger");
  expect(markBoughtError(new StructuredApiError(409, { detail: "The receipt upload is invalid.", code: "receipt_invalid" }))).toContain("Choose the file again");
  expect(markBoughtError(new StructuredApiError(403, { detail: "nope" }))).toContain("can't record spending");
});
