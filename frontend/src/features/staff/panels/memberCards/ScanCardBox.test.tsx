import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ScanCardBox } from "./ScanCardBox";
const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../../lib/api", async () => ({ ...await vi.importActual("../../../../lib/api"), staffRequest }));
describe("card scan privacy", () => {
  it("never displays identity fields for a refused card, including recent checks", async () => {
    staffRequest.mockResolvedValue({ outcome: "revoked", printed_name: "Private holder", card_number: "PRIVATE-123",
      photo_url: "https://example.test/private.jpg" });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}><ScanCardBox makerspaceId={7} /></QueryClientProvider>);
    try {
      fireEvent.change(screen.getByRole("searchbox", { name: "Card payload" }), { target: { value: "physical-card-token" } });
      fireEvent.click(screen.getByRole("button", { name: "Find" }));
      await waitFor(() => expect(screen.getByRole("button", { name: "Next card" })).toBeVisible());
      expect(screen.queryByText("Private holder")).not.toBeInTheDocument();
      expect(screen.queryByText("PRIVATE-123")).not.toBeInTheDocument();
      expect(screen.queryByRole("img")).not.toBeInTheDocument();
      expect(screen.getAllByText("Card revoked — do not accept it.")).toHaveLength(2);
      fireEvent.click(screen.getByRole("button", { name: "Next card" }));
      await waitFor(() => expect(screen.queryByRole("button", { name: "Next card" })).not.toBeInTheDocument());
    } finally { view.unmount(); client.clear(); }
  });
});
