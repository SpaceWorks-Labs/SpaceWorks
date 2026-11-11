import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { MemberPaymentOffline, type OfflineCollection } from "./MemberPaymentOffline";

vi.mock("zxing-wasm/writer", () => ({ setZXingModuleOverrides: vi.fn(), writeBarcode: vi.fn(() => Promise.resolve({})) }));

function wrap(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

const upi = { vpa: "space@okbank", payee_name: "Lab", amount: "250.00", currency: "inr", reference: "SW-9", uri: "upi://pay?pa=space@okbank" };

describe("MemberPaymentOffline unit instructions (parity O-B3)", () => {
  it("names the unit above its instructions and shows no UPI QR", () => {
    const offline: OfflineCollection = { upi: null, instructions: "Pay the Kochi treasurer at the meeting.", claim: null, claimable: false,
      instructions_unit: { id: 4, name: "Kochi chapter", code: "KOC" } };
    wrap(<MemberPaymentOffline makerspaceId={3} paymentId={9} offline={offline} />);
    expect(screen.getByText("Payment instructions from Kochi chapter")).toBeInTheDocument();
    expect(screen.getByText("Pay the Kochi treasurer at the meeting.")).toBeInTheDocument();
    expect(screen.queryByText("UPI ID")).not.toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("keeps the space's QR and no unit heading when the unit has no instructions of its own", () => {
    const offline: OfflineCollection = { upi, instructions: "Or pay at the desk.", claim: null, claimable: true, instructions_unit: null };
    wrap(<MemberPaymentOffline makerspaceId={3} paymentId={9} offline={offline} />);
    expect(screen.queryByText(/Payment instructions from/)).not.toBeInTheDocument();
    expect(screen.getByText("space@okbank")).toBeInTheDocument();
  });
});
