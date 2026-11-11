import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { memberRequest } from "../../../lib/api";
import { PayeeCollection } from "./PayeeCollection";
import { payeeContext, payout } from "./testData";
import { expectNoA11yViolations } from "../../../test/axe";
import { templateFields } from "./payeeTemplates";

vi.mock("../../../lib/api", () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }));
afterEach(() => vi.clearAllMocks());
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><PayeeCollection actorId={73} payout={payout} /></QueryClientProvider>);
  return { ...view, client };
}
async function enterBank() {
  await screen.findByLabelText("Country and payment method");
  fireEvent.change(screen.getByLabelText("Country and payment method"), { target: { value: "IN:bank_transfer:in_bank:1" } });
  for (const [label, value] of [["Account holder name", "Private person"], ["Account number", "001234567890"], ["IFSC", "ABCD0123456"], ["Bank name", "Local Bank"]]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
  fireEvent.click(screen.getByLabelText("I checked these details and agree to their use for this reimbursement."));
}
describe("owner payment routing", () => {
  it("preserves leading zeros, uses a closed payload and never caches plaintext", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path, options) => options?.method === "PUT" ? { id: payout.id, version: 4, state: "open" } : payeeContext);
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const { client, container } = mount(); await enterBank();
    await expectNoA11yViolations(container);
    fireEvent.click(screen.getByRole("button", { name: "Submit payment routing" }));
    await waitFor(() => expect(vi.mocked(memberRequest).mock.calls.some(([, options]) => options?.method === "PUT")).toBe(true));
    const call = vi.mocked(memberRequest).mock.calls.find(([, options]) => options?.method === "PUT")!;
    const body = JSON.parse(call[1]!.body as string);
    expect(call[0]).toBe("/member/event-payouts/obligation/payee/");
    expect(body).toMatchObject({ expected_version: 3, expected_payee_version: null, country: "IN", template_key: "in_bank", template_version: 1,
      details: { account_number: "001234567890" }, disclosure_version: 1 });
    expect(body.operation_id).toBe((call[1]!.headers as Record<string, string>)["Idempotency-Key"]);
    expect(body.save_choices).toBeUndefined();
    expect(JSON.stringify(client.getQueryCache().getAll().map(query => query.state.data))).not.toContain("001234567890");
    expect(client.getMutationCache().getAll()).toHaveLength(0);
    expect(storage).not.toHaveBeenCalled(); storage.mockRestore();
  });
  it("clears secrets on method change and window blur without revealing raw errors", async () => {
    vi.mocked(memberRequest).mockResolvedValue(payeeContext);
    mount(); await enterBank();
    fireEvent.change(screen.getByLabelText("Country and payment method"), { target: { value: "IN:upi:in_upi:1" } });
    expect(screen.queryByDisplayValue("001234567890")).toBeNull();
    expect(screen.getByLabelText("Account holder name")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("UPI ID"), { target: { value: "private@bank" } });
    fireEvent.blur(window); expect(screen.getByLabelText("UPI ID")).toHaveValue("");
  });
  it("fails closed when no action is returned and rejects unrecognized/future templates", async () => {
    vi.mocked(memberRequest).mockResolvedValue({ ...payeeContext, allowed_actions: [] });
    mount(); await screen.findByText("Payment routing is not currently requested.");
    expect(screen.queryByLabelText("Country and payment method")).toBeNull();
    expect(templateFields(["IN", "bank_transfer", "in_bank", 2])).toBeNull();
    expect(templateFields(["US", "bank_transfer", "in_bank", 1])).toBeNull();
    expect(templateFields(["ZZ", "bank_transfer", "other_bank", 1])).toBeNull();
  });
  it("retries uncertain routing writes using the same UUID and sanitized error", async () => {
    vi.mocked(memberRequest).mockImplementation(async (_path, options) => {
      if (options?.method === "PUT") throw new Error("001234567890 private backend value");
      return payeeContext;
    });
    mount(); await enterBank();
    fireEvent.click(screen.getByRole("button", { name: "Submit payment routing" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).not.toContain("001234567890");
    fireEvent.click(screen.getByRole("button", { name: "Submit payment routing" }));
    await waitFor(() => expect(vi.mocked(memberRequest).mock.calls.filter(([, opts]) => opts?.method === "PUT")).toHaveLength(2));
    const writes = vi.mocked(memberRequest).mock.calls.filter(([, opts]) => opts?.method === "PUT");
    expect(JSON.parse(writes[0][1]!.body as string).operation_id).toBe(JSON.parse(writes[1][1]!.body as string).operation_id);
  });
  it("does not send values when focus is lost during digest preparation", async () => {
    vi.mocked(memberRequest).mockResolvedValue(payeeContext);
    const original = crypto.subtle.digest.bind(crypto.subtle);
    let complete!: () => void;
    const digest = vi.spyOn(crypto.subtle, "digest").mockImplementation(async (...args) => {
      await new Promise<void>(resolve => { complete = resolve; }); return original(...args);
    });
    mount(); await enterBank(); fireEvent.click(screen.getByRole("button", { name: "Submit payment routing" }));
    fireEvent.blur(window); await act(async () => complete());
    expect(vi.mocked(memberRequest).mock.calls.some(([, opts]) => opts?.method === "PUT")).toBe(false);
    digest.mockRestore();
  });
  it.each([
    ["IN", "upi", "in_upi", ["holder_name", "upi_id"]],
    ["US", "bank_transfer", "us_bank", ["holder_name", "routing_number", "account_number", "account_type"]],
    ["DE", "bank_transfer", "iban_bank", ["holder_name", "iban", "swift", "bank_name"]],
    ["AU", "bank_transfer", "au_bank", ["holder_name", "bank_name", "account_number", "bsb", "swift"]],
    ["CA", "bank_transfer", "ca_bank", ["holder_name", "bank_name", "account_number", "institution_number", "transit_number", "swift"]],
    ["NZ", "bank_transfer", "nz_bank", ["holder_name", "bank_name", "account_number", "bank_code", "branch_code", "swift"]],
    ["IN", "paypal", "email", ["holder_name", "payout_email"]],
    ["IN", "wise", "email", ["holder_name", "payout_email"]],
    ["IN", "cash", "cash", ["holder_name"]],
    ["IN", "cheque", "cheque", ["holder_name", "delivery_instructions"]],
    ["IN", "other", "other", ["holder_name"]],
  ] as const)("exposes only the closed routing fields for %s / %s", (country, method, key, fields) => {
    expect(templateFields([country, method, key, 1])).toEqual(fields);
    expect(templateFields([country, method, key, 1])?.some(field => /tax|password|pin|otp/.test(field))).toBe(false);
  });
});
