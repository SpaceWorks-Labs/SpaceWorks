import type React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";
import { WalletPage } from "../members/wallet/WalletPage";
import { CardVerifyPage } from "./CardVerifyPage";
import { isCardPath } from "./routeNames";

const api = vi.hoisted(() => ({ publicV1Request: vi.fn(), memberRequest: vi.fn(), memberRequestBlob: vi.fn(),
  getAccessToken: vi.fn(() => "token"), refreshAccessToken: vi.fn(() => Promise.resolve()) }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<typeof import("../../lib/api")>("../../lib/api")), ...api }));

function renderAt(path: string, pattern: string, element: React.JSX.Element) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path={pattern} element={element} /></Routes></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { Object.values(api).forEach((mock) => "mockClear" in mock && mock.mockClear()); });

describe("card routes", () => {
  it("recognises only the card paths", () => {
    expect(isCardPath("/verify/c/abc")).toBe(true);
    expect(isCardPath("/o/makers/ids/student-id")).toBe(true);
    expect(isCardPath("/member/cards")).toBe(true);
    expect(isCardPath("/m/tinker/member/cards/accept")).toBe(true);
    expect(isCardPath("/member/account")).toBe(false);
    expect(isCardPath("/verify")).toBe(false);
  });
});

describe("CardVerifyPage", () => {
  it("says a revoked card is not valid and shows only what the holder allowed", async () => {
    api.publicV1Request.mockResolvedValue({ status: "revoked", valid: false, issuer: { kind: "space", name: "Tinkerspace", logo_url: null },
      label: "Member", number: "TNK-0042", valid_until: null, holder: null, note: "", checked_at: "2026-11-03T10:00:00Z" });
    renderAt("/verify/c/tok123", "/verify/c/:token", <CardVerifyPage />);
    expect(await screen.findByText("Revoked card")).toBeVisible();
    expect(screen.getByText("This card has been cancelled by its issuer.")).toBeVisible();
    expect(screen.getAllByText(/Tinkerspace/)[0]).toBeVisible();
    expect(screen.queryByText("TNK-0042")).not.toBeInTheDocument();
    expect(api.publicV1Request).toHaveBeenCalledWith("/public/card-verifications/tok123");
    expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toContain("noindex");
  });

  it("answers a hidden card with the same not-found page", async () => {
    api.publicV1Request.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
    renderAt("/verify/c/nope", "/verify/c/:token", <CardVerifyPage />);
    expect(await screen.findByText("Card not found")).toBeVisible();
  });
});

describe("WalletPage", () => {
  it("shows the ticket view with the desk QR and its caption", async () => {
    api.memberRequest.mockImplementation((path: string) => Promise.resolve(path === "/auth/me" ? { id: 3 } : [{
      kind: "member_card", id: 4, makerspace_id: 7, issuer: "Tinkerspace", title: "Member card", name: "Priya Raman",
      number: "TNK-0042", label: "Monthly", valid_until: "31 Dec 2026", status: "valid", has_back: false, check_url: "",
      photo_request_open: false, wallet_platforms: [], email_available: true, qr_image: "data:image/png;base64,AAAA" }]));
    renderAt("/member/cards", "/member/cards", <WalletPage />);
    expect(await screen.findByText("Priya Raman")).toBeVisible();
    expect(screen.getByAltText("Desk QR code")).toBeVisible();
    expect(screen.getByText("Show this at the desk. It only holds a private member link.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Email me my card" }));
    await waitFor(() => expect(api.memberRequest).toHaveBeenCalledWith("/member/cards/member_card/4/email", { method: "POST" }));
  });
});
