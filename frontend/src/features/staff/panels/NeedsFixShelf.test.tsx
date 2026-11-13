import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { NeedsFixShelf } from "./NeedsFixShelf";
import type { Makerspace } from "./shared";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
it("confirms the named quantity before scrapping units", async () => {
 request.mockImplementation(async (_path, init) => init?.method === "POST" ? {} : { results: [{ id: 4, name: "Multimeter", needs_fix_quantity: 2, available_quantity: 3, total_quantity: 5 }] });
 render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><NeedsFixShelf makerspace={{ id: 7 } as Makerspace} /></QueryClientProvider>);
 fireEvent.click(await screen.findByRole("button", { name: "Actions for Multimeter" }));
 fireEvent.click(screen.getByRole("menuitem", { name: "Scrap…" }));
 expect(request).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "POST" }));
 expect(screen.getByRole("dialog", { name: "Scrap 2 × Multimeter?" })).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button", { name: "Scrap" }));
 await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/inventory/4/needs-fix", { method: "POST", body: JSON.stringify({ action: "scrap", quantity: 2 }) }));
});
