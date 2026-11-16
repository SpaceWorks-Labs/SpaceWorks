import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BillingDocumentsSettings } from "./BillingDocumentsSettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
const policy = { number_prefix: "", bill_prefix: "BILL-", payment_instructions: "Pay at the desk", legal_name: "", address: "", tax_id: "", footer: "", account_codes: { income: "4000", cash: "1000", online: "1010", deposit: "2100" }, payment_terms_days: 14 };

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
    <BillingDocumentsSettings makerspaceId={7} />
  </QueryClientProvider>);
  fireEvent.click(screen.getByRole("button", { name: "Configure documents" }));
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue(policy); });

describe("Core billing documents settings", () => {
  it("saves presentation and mapping without rewriting billing terms", async () => {
    mount();
    fireEvent.change(await screen.findByLabelText("Number prefix"), { target: { value: "SW-" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/billing-settings", {
      method: "PATCH", body: JSON.stringify({ number_prefix: "SW-", bill_prefix: "BILL-", payment_instructions: "Pay at the desk", legal_name: "", address: "", tax_id: "", footer: "", account_codes: policy.account_codes }),
    }));
  });

  it("keeps invalid mapping JSON from reaching the server", async () => {
    mount();
    fireEvent.change(await screen.findByLabelText("Accounting account codes (JSON)"), { target: { value: "{" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledTimes(1);
  });

  it("saves the bill prefix and offline payment instructions", async () => {
    mount();
    fireEvent.change(await screen.findByLabelText("Bill prefix"), { target: { value: "INV-" } });
    fireEvent.change(screen.getByLabelText("Payment instructions"), { target: { value: "Bring cash to reception." } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
    const payload = JSON.parse(staffRequest.mock.calls[1][1].body);
    expect(payload.bill_prefix).toBe("INV-");
    expect(payload.payment_instructions).toBe("Bring cash to reception.");
    expect(payload).not.toHaveProperty("next_bill_number");
  });
});
