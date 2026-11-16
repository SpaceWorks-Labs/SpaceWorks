import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { DirectLoans } from "./DirectLoans";
const { list } = vi.hoisted(() => ({ list: vi.fn() }));
vi.mock("../../lib/usePaginatedQuery", () => ({ usePaginatedQuery: list }));
vi.mock("./StaffPanels", () => ({ useStaffGet: () => ({ data: { results: [] }, isLoading: false }) }));
vi.mock("./quickCreate", () => ({ useQuickCreate: () => undefined }));
vi.mock("./useDirectLoanReturn", () => ({ useDirectLoanReturn: () => ({ returningLoan: null }) }));
vi.mock("./DirectLoanReturnModal", () => ({ DirectLoanReturnModal: () => null }));
vi.mock("./handover/DirectHandoverWizard", () => ({ DirectHandoverWizard: ({ onClose }: { onClose: () => void }) => <div role="dialog" aria-label="Handout task"><button onClick={onClose}>Close task</button></div> }));
vi.mock("../inventory/KitChecklist", () => ({ useKitChecklist: () => ({ ready: true, counts: [] }), KitChecklistCapture: () => null }));
const makerspace = { id: 1, name: "Lab", slug: "lab", public_code: "LAB1", telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false };
beforeEach(() => { list.mockReturnValue({ results: [], count: 0, page: 1, pageSize: 24, setPage: vi.fn(), isLoading: false, isError: false }); });
function mount(url: string) {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={[url]}><DirectLoans makerspace={makerspace} /></MemoryRouter></QueryClientProvider>);
}
it("keeps returned-tab pages separate under the existing query prefix and preserves other URL parameters", () => {
  mount("/admin/direct?handout=returned&source=desk");
  expect(list).toHaveBeenCalledWith(expect.objectContaining({ key: ["direct-loans", 1, "returned"], path: "/admin/makerspace/1/direct-loans?status=returned" }));
  expect(screen.getByRole("link", { name: "Claim codes" })).toHaveAttribute("href", "?handout=claim-codes&source=desk");
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("opens the issue form as a task from the on-loan list", () => {
  mount("/admin/direct");
  expect(list).toHaveBeenCalledWith(expect.objectContaining({ key: ["direct-loans", 1, "checked_out"], path: "/admin/makerspace/1/direct-loans?status=checked_out" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(screen.getAllByRole("button", { name: "New handout" })[0]);
  expect(screen.getByRole("dialog", { name: "Handout task" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close task" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});
