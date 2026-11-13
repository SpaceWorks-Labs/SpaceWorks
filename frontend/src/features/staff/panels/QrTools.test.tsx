import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { QrTools } from "./QrTools";
import type { Makerspace } from "./shared";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request, downloadStaffFile: vi.fn() }));
it("switches label modes and restricts unit choices to individually tracked items", async () => {
 request.mockImplementation(async path => path === "/admin/qr-print-batches/3" ? { id: 3, title: "Workshop labels", items: [] } :
   { results: path.includes("/inventory?") ? [{ id: 1, name: "Screws", tracking_mode: "quantity", available_quantity: 20 }, { id: 2, name: "Drill", tracking_mode: "individual", available_quantity: 4 }] : [] });
 render(<MemoryRouter initialEntries={["/admin/qr-tools?batch=3"]}><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><QrTools makerspace={{ id: 7, enabled_modules: ["asset_units"] } as Makerspace} /></QueryClientProvider></MemoryRouter>);
 await screen.findByRole("radio", { name: "Item" });
 await screen.findByRole("option", { name: /Screws/ });
 fireEvent.click(screen.getByRole("radio", { name: "Units" }));
 expect(screen.getByRole("radio", { name: "Units" })).toHaveAttribute("aria-checked", "true");
 expect(screen.queryByRole("option", { name: /Screws/ })).not.toBeInTheDocument();
 expect(screen.getByRole("option", { name: /Drill/ })).toBeInTheDocument();
 fireEvent.click(screen.getByRole("radio", { name: "Reprint a unit" }));
 expect(screen.getByLabelText("Inventory item")).toHaveValue("");
});
