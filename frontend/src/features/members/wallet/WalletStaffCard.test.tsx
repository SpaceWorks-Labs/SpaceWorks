import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { MyCard } from "./api";
import { WalletPage } from "./WalletPage";

const staffCard: MyCard = { kind: "staff_card", id: 4, makerspace_id: 2, issuer: "Tinkerspace", title: "Staff card",
  name: "Asha Menon", number: "STF-0001", label: "Staff: Space Manager", valid_until: "", status: "valid", has_back: false,
  check_url: "https://example.test/verify/c/tok", photo_request_open: false, wallet_platforms: [], email_available: false,
  qr_image: null, photo_set: false, photo_cleanup_available: false, photo_aspect: 0.8 };

vi.mock("./api", async () => ({ ...(await vi.importActual<object>("./api")),
  useMemberIdentity: () => ({ restoring: false, identity: { data: { id: 1 }, isLoading: false, error: null } }),
  useMyCards: () => ({ data: [staffCard], isLoading: false, error: null }),
  useWalletPass: () => ({ isPending: false, error: null, mutate: vi.fn() }),
  useEmailMyCard: () => ({ isPending: false, isSuccess: false, error: null, mutate: vi.fn() }) }));

describe("My cards: a staff card", () => {
  it("offers downloads and the check page, but no e-mail, photo or extras settings", () => {
    render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><WalletPage /></MemoryRouter></QueryClientProvider>);
    expect(screen.getByRole("heading", { name: "Staff card" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Check page" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Email me my card" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Card settings" })).not.toBeInTheDocument();
  });
});
