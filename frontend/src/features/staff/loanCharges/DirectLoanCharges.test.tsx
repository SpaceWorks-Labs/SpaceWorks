import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DirectLoanList, type DirectLoan } from "../DirectLoanList";
import { useDirectLoanReturn } from "../useDirectLoanReturn";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

const loan: DirectLoan = { id: 8, request_id: 41, public_token: "t", status: "returned", target_label: "Ada", due_at: null,
  issued_by: null, items: [{ product_name: "Drill", quantity: 1 }], return_scan_required: false };
const makerspace = { id: 7, name: "Lab", slug: "lab", public_code: "LAB", telegram_group_chat_id: "", frontend_domain: null,
  // #184 G5 (0acf6df0): the damage step needs loan charges tracked as well as price lists.
  hidden_from_central_directory: false, enabled_features: ["charges.enabled", "charges.loans", "charges.pricing"], enabled_modules: ["request_workflow"] };

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => { staffRequest.mockReset(); });

describe("Direct handout charges", () => {
  it("offers a Charges disclosure on each handout that fetches only when opened", async () => {
    staffRequest.mockResolvedValue({ request_id: 41, currency: "usd", pricing_enabled: true, waivers_enabled: false,
      can_waive: false, charges: [], waivers: [], accountability: [] });
    render(<DirectLoanList loans={[loan]} onReturn={() => {}} makerspaceId={7} />, { wrapper });
    expect(staffRequest).not.toHaveBeenCalled();
    const summary = screen.getByText("Charges");
    fireEvent.click(summary);
    summary.closest("details")!.open = true;
    fireEvent(summary.closest("details")!, new Event("toggle"));
    expect(await screen.findByText("No charges on this loan.")).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/requests/41/charges");
  });

  it("opens the charge step after a return that recorded damage, not after a clean one", async () => {
    staffRequest.mockResolvedValue(loan);
    const { result } = renderHook(() => useDirectLoanReturn(makerspace), { wrapper });
    const submit = async (damaged: number) => {
      act(() => { result.current.openReturnModal({ ...loan, status: "checked_out" }); result.current.setReturnEvidenceId(3); result.current.setReturnNotes("Back"); });
      act(() => result.current.submitReturn([{ item_id: 4, returned: 1 - damaged, damaged, missing: 0 }]));
      await waitFor(() => expect(result.current.pending).toBe(false));
    };
    await submit(0);
    expect(result.current.chargeRequestId).toBeNull();
    await submit(1);
    await waitFor(() => expect(result.current.chargeRequestId).toBe(41));
    act(() => result.current.closeChargeStep());
    expect(result.current.chargeRequestId).toBeNull();
  });
});
