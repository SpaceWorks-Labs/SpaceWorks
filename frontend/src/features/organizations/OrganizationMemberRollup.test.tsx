import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OrganizationMemberRollup, type MemberRollup } from "./OrganizationMemberRollup";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

const ROLLUP: MemberRollup = {
  people: { total: 1240, explicit: 40, derived_only: 1200, owned_spaces: 2 },
  spaces: [{ name: "Harbour Lab", slug: "harbour", active: 900, revoked: 12 }, { name: "North Shop", slug: "north", active: 310, revoked: 0 }],
  home_space_card_note: "Member cards are issued by the home space.",
};

function show(data: MemberRollup) {
  staffRequest.mockResolvedValue(data);
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <OrganizationMemberRollup organizationId={3} />
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("OrganizationMemberRollup", () => {
  it("shows the de-duplicated total split into invited members and members through owned spaces", async () => {
    show(ROLLUP);
    const total = (await screen.findByText("People in total")).parentElement!;
    expect(within(total).getByText("1,240")).toBeInTheDocument();
    expect(within(screen.getByText("Invited members").parentElement!).getByText("40")).toBeInTheDocument();
    const derived = screen.getByText("Through owned spaces").parentElement!;
    expect(within(derived).getByText("1,200")).toBeInTheDocument();
    expect(within(derived).getByText(/the 2 spaces it owns/)).toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/organizations/3/member-rollup/");
  });

  it("lists each owned space with active and revoked counts, and nothing that names a person", async () => {
    show(ROLLUP);
    const table = await screen.findByRole("table", { name: /each space the organization owns/ });
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByRole("rowheader", { name: "Harbour Lab" })).toBeInTheDocument();
    expect(within(rows[1]).getByText("900")).toBeInTheDocument();
    expect(within(rows[1]).getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/Counts only: names stay with each space/)).toBeInTheDocument();
  });

  it("explains an organization that owns no spaces", async () => {
    show({ ...ROLLUP, people: { total: 4, explicit: 4, derived_only: 0, owned_spaces: 0 }, spaces: [] });
    expect(await screen.findByText(/owns no spaces yet/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });
});
