import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { draftFrom, EventMoneySettings, payloadFrom } from "./EventMoneySettings";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest }));

const settings = { makerspace_id: 2, version: 3, prize_tds_enabled: false, prize_tds_rate: "30.00", prize_tds_threshold: "10000.00",
  payee_templates: [], available_payee_templates: [["IN", "bank_transfer"], ["IN", "upi"]], currency: "inr" };

function wrap() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><EventMoneySettings makerspaceId={2} /></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation((_path: string, init?: RequestInit) =>
  Promise.resolve(init?.method === "PATCH" ? { ...settings, version: 4, ...JSON.parse(String(init.body)) } : settings)); });

describe("event money settings (#181 G7, G13)", () => {
  it("round-trips a draft into a versioned patch with country/method pairs", () => {
    const draft = { ...draftFrom(settings), prize_tds_enabled: true, payee_templates: ["IN:upi"] };
    expect(payloadFrom(draft, 3)).toEqual({ expected_version: 3, prize_tds_enabled: true, prize_tds_rate: "30.00",
      prize_tds_threshold: "10000.00", payee_templates: [["IN", "upi"]] });
  });

  it("is record only, off by default, and saves the chosen payee options", async () => {
    wrap();
    fireEvent.click(screen.getByRole("button", { name: "Configure prize tax and payees" }));
    const toggle = await screen.findByRole("checkbox", { name: /Record prize tax \(TDS\)/ });
    expect(toggle).not.toBeChecked();
    expect(screen.getByText(/No certificates or filing reports are produced/)).toBeInTheDocument();
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("checkbox", { name: /IN · UPI/ }));
    fireEvent.submit(toggle.closest("form")!);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/2/event-money-settings",
      expect.objectContaining({ method: "PATCH" })));
    const body = JSON.parse(String(staffRequest.mock.calls.find(call => call[1]?.method === "PATCH")![1].body));
    expect(body).toMatchObject({ expected_version: 3, prize_tds_enabled: true, payee_templates: [["IN", "upi"]] });
  });
});
