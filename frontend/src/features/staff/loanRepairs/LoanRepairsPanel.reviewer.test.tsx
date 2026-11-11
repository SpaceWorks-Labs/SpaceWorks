import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { LoanRepairsPanel } from "./LoanRepairsPanel";
import type { LoanRepairLine } from "./loanRepairsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api"), staffRequest }));

const line: LoanRepairLine = { accountability_id: 31, product_name: "Drill", quantity: 1, asset_tag: "", remark: "Bent chuck",
  evidence_id: null, handed_off: false, issue: null };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><LoanRepairsPanel loan={{ id: 9, status: "returned", makerspace_id: 7 }} /></QueryClientProvider>);
}

it("lets a request reviewer send a damaged line to repairs, then shows it as In repairs without detail", async () => {
  let lines = [line];
  staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => {
    if (init?.method === "POST") { lines = [{ ...line, handed_off: true }]; return { created: true, issue_id: 12, line: lines[0] }; }
    return { request_id: 9, lines };
  });
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Send Drill · 1 damaged to repairs" }));
  expect(await screen.findByText("In repairs")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /to repairs/ })).toBeNull();
  expect(screen.queryByText(/Repair #/)).toBeNull();
  await waitFor(() => expect(JSON.parse(String(staffRequest.mock.calls.find(([, init]) => init?.method === "POST")?.[1]?.body)))
    .toEqual({ accountability_id: 31 }));
});
