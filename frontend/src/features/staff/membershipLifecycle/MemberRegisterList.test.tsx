import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { MemberRegisterList } from "./MemberRegisterList";

vi.mock("../../../lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const ROWS = [
  { membership_id: 1, unit: null, member_number: "TNK-0001", name: "Asha Rao", email: "asha@example.org", plan: "Annual", standing: "active", term_ends_at: "2027-03-31T00:00:00Z", source: "join", joined_at: "2026-01-04T00:00:00Z" },
  { membership_id: 2, unit: null, member_number: "TNK-0002", name: "Bilal Khan", email: "bilal@example.org", plan: "Annual", standing: "lapsed", term_ends_at: "2026-09-30T00:00:00Z", source: "import", joined_at: "2025-08-01T00:00:00Z" },
];

function answer(path: string, init?: RequestInit) {
  if (path.includes("/member-register/bulk")) {
    const body = JSON.parse(String(init?.body));
    return Promise.resolve((body.membership_ids ?? ROWS.map((row) => row.membership_id)).map((id: number) => ({ id, ok: id === 1, code: id === 1 ? "" : "not_due" })));
  }
  if (path.includes("/member-register")) return Promise.resolve(ROWS);
  if (path.includes("/saved-views")) return Promise.resolve({ count: 0, next: null, previous: null, results: [] });
  return Promise.resolve([]);
}

function show(props: Partial<React.ComponentProps<typeof MemberRegisterList>> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter>
    <MemberRegisterList makerspaceId={9} {...props} />
  </MemoryRouter></QueryClientProvider>);
}
const registerCalls = () => vi.mocked(staffRequest).mock.calls.map(([path]) => String(path)).filter((path) => path.includes("/member-register") && !path.includes("/bulk"));

beforeEach(() => { vi.mocked(staffRequest).mockReset(); vi.mocked(staffRequest).mockImplementation(answer as typeof staffRequest); });

describe("member register (parity O-B2)", () => {
  it("narrows by a standing chip through the shared filter contract", async () => {
    show();
    expect(await screen.findByText("Asha Rao")).toBeVisible();
    expect(registerCalls()[0]).toBe("/admin/makerspaces/9/member-register");
    fireEvent.click(screen.getByRole("button", { name: "Lapsed" }));
    await waitFor(() => expect(registerCalls()).toContain("/admin/makerspaces/9/member-register?chip=lapsed"));
    expect(screen.getByRole("button", { name: "Lapsed" })).toHaveAttribute("aria-pressed", "true");
  });

  it("reads an old ?standing= deep link as its chip", async () => {
    show({ initialStanding: "ending_soon" });
    await waitFor(() => expect(registerCalls()[0]).toBe("/admin/makerspaces/9/member-register?chip=expiring"));
    expect(screen.getByRole("button", { name: "Ending in 30 days" })).toHaveAttribute("aria-pressed", "true");
  });

  it("only offers the changes chip while ask-for-changes is on", async () => {
    show();
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("button", { name: "Changes requested" })).toBeNull();
  });

  it("applies a bulk action and shows a result for every member", async () => {
    show({ features: ["membership.register_bulk", "membership.renewal_desk"] });
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByRole("checkbox", { name: "Select all rows" }));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "send_reminder" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to 2" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/9/member-register/bulk",
      { method: "POST", body: JSON.stringify({ action: "send_reminder", membership_ids: [1, 2] }) }));
    const results = await screen.findByRole("region", { name: "Bulk action results" });
    expect(within(results).getByRole("status")).toHaveTextContent("Done for 1 of 2. 1 not changed.");
    const lines = within(results).getAllByRole("row").slice(1).map((line) => line.textContent);
    expect(lines).toEqual(["Bilal KhanNot due for a reminder today", "Asha RaoDone"]);
  });

  it("applies one action to every match by filter, after a count confirmation", async () => {
    show({ features: ["membership.register_bulk", "membership.renewal_desk"] });
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByRole("button", { name: "Lapsed" }));
    await screen.findByText("Asha Rao");
    fireEvent.click(screen.getByRole("checkbox", { name: "Select row 1" }));
    fireEvent.change(screen.getByLabelText("Bulk action"), { target: { value: "send_reminder" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply to all 2 matching" }));
    expect(screen.getByRole("alertdialog")).toHaveTextContent("all 2 members matching");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspaces/9/member-register/bulk", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "Yes, apply to 2" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/9/member-register/bulk",
      { method: "POST", body: JSON.stringify({ action: "send_reminder", filter: { chip: "lapsed" } }) }));
    expect(await screen.findByRole("region", { name: "Bulk action results" })).toBeVisible();
  });

  it("hides bulk selection without the switch", async () => {
    show({ features: ["membership.renewal_desk"] });
    await screen.findByText("Asha Rao");
    expect(screen.queryByRole("checkbox", { name: "Select all rows" })).toBeNull();
  });
});
