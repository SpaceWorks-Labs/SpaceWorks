import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { QrLabelPrinterSend } from "./QrLabelPrinterSend";
import { RefillConsumableDialog } from "./RefillConsumableDialog";
import type { ToBuyItem } from "./ProcurementPanelRows";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{node}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("RefillConsumableDialog", () => {
  it("credits the grams received back to the source consumable", async () => {
    staffRequest.mockResolvedValue({});
    const onDone = vi.fn();
    wrap(<RefillConsumableDialog item={{ id: 8, name: "PLA spool" } as ToBuyItem} onClose={vi.fn()} onDone={onDone} />);
    const submit = screen.getByRole("button", { name: "Refill" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Amount received (grams)"), { target: { value: "1000" } });
    fireEvent.click(submit);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/procurement/to-buy/8/refill-consumable",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ amount: "1000" }) })));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });
});

describe("QrLabelPrinterSend", () => {
  const printer = { id: "d1", makerspace: 4, name: "Zebra desk", kind: "label_printer", status: "active" };
  it("sends the batch to the active label printer and shows the history", async () => {
    staffRequest.mockImplementation((path: string, init?: RequestInit) => {
      if (String(path).includes("/devices")) return Promise.resolve({ count: 2, results: [printer, { ...printer, id: "d2", kind: "printer", name: "Prusa" }] });
      if (init?.method === "POST") return Promise.resolve({ id: "c1" });
      return Promise.resolve({ count: 0, results: [] });
    });
    wrap(<QrLabelPrinterSend makerspaceId={4} batchId={12} hasItems />);
    expect(await screen.findByRole("option", { name: "Zebra desk" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Prusa" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Send to printer" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/qr-print-batches/12/label-commands", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(staffRequest.mock.calls.find(call => call[1]?.method === "POST")![1].body);
    expect(body.device_id).toBe("d1");
    expect(body.request_id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("explains when no label printer is enrolled", async () => {
    staffRequest.mockResolvedValue({ count: 0, results: [] });
    wrap(<QrLabelPrinterSend makerspaceId={4} batchId={12} hasItems />);
    expect(await screen.findByText("No active label printer is enrolled. Add one under Devices.")).toBeInTheDocument();
  });
});
