import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import { Inventory } from "./Inventory";
import { Categories } from "./Categories";
import { ContainersPanel } from "./ContainersPanel";
import { NeedsFixShelf } from "./NeedsFixShelf";
import { StocktakePanel } from "./StocktakeSessionPanel";
import { StockTransferPanel } from "./StockTransferPanel";
import { ProcurementPanel } from "./ProcurementPanel";
import { Ledger } from "./Ledger";
import { WarrantyPanel } from "./WarrantyPanel";
import { QrTools } from "./QrTools";
import { ScannerPanel } from "./ScannerPanel";
import { BulkImport } from "./BulkImport";
import type { Makerspace } from "./shared";
const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request, downloadStaffFile: vi.fn() }));
const space = { id: 7, slug: "forge", name: "Forge", enabled_features: [], enabled_modules: [] } as unknown as Makerspace;
function setup(element: React.ReactNode) {
 return render(<MemoryRouter><QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{element}</QueryClientProvider></MemoryRouter>);
}
beforeEach(() => { request.mockImplementation(async path => path === "/auth/me" ? { makerspaces: [] } : path.includes("/to-buy?limit") ? [] : { count: 0, results: [] }); });
it.each([
 ["Inventory", <Inventory makerspace={space} />], ["Categories", <Categories makerspace={space} />],
 ["Containers", <ContainersPanel makerspace={space} canEditInventory />], ["Repair shelf", <NeedsFixShelf makerspace={space} />],
 ["Stocktake", <StocktakePanel makerspace={space} />], ["Transfers", <StockTransferPanel makerspace={space} makerspaces={[]} isSuperadmin={false} canEditInventory />],
 ["To buy", <ProcurementPanel makerspace={space} />], ["Ledger", <Ledger makerspace={space} isSuperadmin={false} />],
 ["Warranties", <WarrantyPanel makerspace={space} canEditInventory />], ["QR labels", <QrTools makerspace={space} />],
 ["Scanner", <ScannerPanel makerspace={space} makerspaces={[]} isSuperadmin={false} />], ["Bulk import", <BulkImport makerspace={space} />],
])("%s has one page heading and accessible empty-state controls", async (title, element) => {
 const { container } = setup(element);
 await waitFor(() => expect(container.querySelector('[aria-label="Loading content"]')).not.toBeInTheDocument());
 expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
 expect(screen.getByRole("heading", { level: 1, name: title })).toBeInTheDocument();
 await expectNoA11yViolations(container);
});
it("offers Retry for a failed inventory load and recovers in the same view", async () => {
 let failed = true;
 request.mockImplementation(async () => { if (failed) throw new Error("Network error"); return { count: 0, results: [] }; });
 setup(<Inventory makerspace={space} />);
 expect(await screen.findByText("Couldn't load inventory. Try again.")).toBeInTheDocument();
 failed = false;
 fireEvent.click(screen.getByRole("button", { name: "Retry" }));
 expect(await screen.findByText("No parts added yet. Add your first item.")).toBeInTheDocument();
});
