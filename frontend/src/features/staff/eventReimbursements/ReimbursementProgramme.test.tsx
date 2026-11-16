import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render as rtlRender, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
// The crew budget pool (e3bcaa04) mounts query-backed commands, so the render needs a client.
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  return rtlRender(ui, { wrapper, ...options });
}
import contract from "../../../../../backend/tests/events/programme/contracts/reimbursement_addon.json";
import { ReimbursementProgramme } from "./ReimbursementProgramme";
const mutate = vi.hoisted(() => vi.fn());
vi.mock("./api", () => ({ reimbursementAdminPath: () => "/admin/events/41/reimbursements/", reimbursementAdminKey: () => ["event-reimbursements", 41], useProgramme: () => ({ data: { initialized: false, allowed_actions: ["programme_initialize"] } }),
  useProgrammeCommand: () => ({ mutate, isPending: false, error: null }) }));
afterEach(() => { mutate.mockReset(); });
describe("finance programme initialization", () => {
  it("uses the frozen create-or-get contract and always starts disabled", () => {
    render(<ReimbursementProgramme scope={{ actorId: 1, makerspaceId: 2, eventId: 41 }} />);
    fireEvent.change(screen.getByLabelText("Initial total (INR)"), { target: { value: String(contract.initialization.payload.initial_total_minor / 100) } });
    const target = new Date(contract.initialization.payload.initial_settings.claim_due_at);
    const local = new Date(target.getTime() - target.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    fireEvent.change(screen.getByLabelText("Claim deadline (your local time)"), { target: { value: local } });
    fireEvent.submit(screen.getByRole("button", { name: "Create programme and initial pool" }).closest("form")!);
    const { operation_id: _id, ...body } = contract.initialization.payload;
    expect(mutate).toHaveBeenCalledWith({ path: "/admin/events/41/reimbursements/programme/", body }, expect.anything());
    expect(screen.queryByRole("checkbox", { name: "Enable support requests" })).toBeNull();
  });
});
