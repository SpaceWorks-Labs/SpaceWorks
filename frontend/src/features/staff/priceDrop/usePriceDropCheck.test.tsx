import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import type { PriceDropReport } from "./priceDropApi";
import { usePriceDropCheck } from "./usePriceDropCheck";

vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn() }));

const ON = [{ id: 3, enabled_modules: [], enabled_features: ["charges.price_drop_refunds"] }];
const OFF = [{ id: 3, enabled_modules: [], enabled_features: [] }];

const report = (count = 1): PriceDropReport => ({
  count, truncated: false, totals: [{ currency: "usd", difference: "10.00" }],
  items: count ? [{ area: "bookings", item_type: "booking", item_id: 12, label: "Laser room", starts_at: null,
    payment_id: 40, currency: "usd", paid: "30.00", before: "30.00", after: "20.00", difference: "10.00", case_id: null }] : [],
});

let result: Promise<boolean> | null = null;

function Harness() {
  const drop = usePriceDropCheck(3);
  return <div>
    <button type="button" onClick={() => { result = drop.check("/admin/spaces/12/", "PATCH", { payment_amount: "20.00" }); }}>
      Save</button>
    {drop.dialog}
  </div>;
}

function show(spaces: unknown) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["staff", "makerspaces"], spaces);
  return render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>);
}

describe("usePriceDropCheck", () => {
  beforeEach(() => { vi.mocked(staffRequest).mockReset(); result = null; });

  it("saves straight away and asks nothing while price-drop refunds are off", async () => {
    show(OFF);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await expect(result).resolves.toBe(true);
    expect(staffRequest).not.toHaveBeenCalled();
  });

  it("previews the same request and lets the save go ahead when nothing paid gets cheaper", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ price_drop: report(0) });
    show(ON);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await expect(result).resolves.toBe(true);
    expect(staffRequest).toHaveBeenCalledWith("/admin/spaces/12/?price_drop_preview=1",
      { method: "PATCH", body: JSON.stringify({ payment_amount: "20.00" }) });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("lists the paid items with the difference and saves only when confirmed", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ price_drop: report() });
    show(ON);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Lower this price?")).toBeVisible();
    expect(screen.getByText(/Booking · Laser room/)).toBeVisible();
    expect(screen.getByText(/approves every refund/)).toBeVisible();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save and open refunds" })); });
    await expect(result).resolves.toBe(true);
  });

  it("keeps editing when the person backs out", async () => {
    vi.mocked(staffRequest).mockResolvedValue({ price_drop: report() });
    show(ON);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Lower this price?");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Keep editing" })); });
    await expect(result).resolves.toBe(false);
  });

  it("goes ahead when the preview cannot answer, so the real save shows its own error", async () => {
    vi.mocked(staffRequest).mockRejectedValue(Object.assign(new Error("Off"), { status: 404 }));
    show(ON);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await expect(result).resolves.toBe(true);
  });
});
