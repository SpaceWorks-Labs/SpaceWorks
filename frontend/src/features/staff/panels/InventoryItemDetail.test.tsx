import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { InventoryItemDetail } from "./InventoryItemDetail";
import { emptyAdjust, formFromProduct, type AdminProduct } from "./InventoryPanelShared";
import type { Makerspace } from "./shared";
const product = { id: 27, name: "Drill", description: "", tracking_mode: "quantity", category: null, total_quantity: 20, available_quantity: 4, issued_quantity: 16, damaged_quantity: 0, lost_quantity: 0, is_public: true, show_public_count: false, public_availability_mode: "status_only", is_archived: false } as AdminProduct;
function Editor() {
 const [form, setForm] = useState(formFromProduct(product));
 const [adjustForm, setAdjustForm] = useState(emptyAdjust);
 return <InventoryItemDetail product={product} makerspace={{ id: 7, slug: "forge" } as Makerspace} canViewAudit={false} kitEnabled={false}
   form={form} setForm={setForm} categories={[]} onClose={() => {}} pending={false} onSave={() => {}} onArchive={() => {}}
   adjustForm={adjustForm} setAdjustForm={setAdjustForm} adjustPending={false} onAdjust={() => {}} invalidate={() => {}} />;
}
it("keeps a dirty item draft across URL tabs and Discard restores its values", () => {
 render(<MemoryRouter initialEntries={["/admin/inventory?item=27"]}><QueryClientProvider client={new QueryClient()}><Editor /></QueryClientProvider></MemoryRouter>);
 fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Cordless drill" } });
 expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
 fireEvent.click(screen.getByRole("link", { name: "Stock" }));
 expect(screen.getByRole("heading", { name: "Adjust quantities" })).toBeInTheDocument();
 fireEvent.click(screen.getByRole("link", { name: "Details" }));
 expect(screen.getByLabelText("Name")).toHaveValue("Cordless drill");
 fireEvent.click(screen.getByRole("button", { name: "Discard" }));
 expect(screen.getByLabelText("Name")).toHaveValue("Drill");
 expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
 expect(screen.queryByRole("link", { name: "History" })).not.toBeInTheDocument();
 expect(screen.queryByRole("link", { name: "Custody" })).not.toBeInTheDocument();
});
