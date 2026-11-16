import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Ledger } from "./Ledger";
import { LinkedJob } from "./machine/LinkedJob";
import { reportArea, reportAreaGroups } from "./reportAreas";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

const makerspace = { id: 7, name: "Lab", slug: "lab" } as never;
function mount(node: React.ReactNode, entry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[entry]}><QueryClientProvider client={client}>{node}</QueryClientProvider></MemoryRouter>);
}
beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

describe("decision 259 deep links", () => {
  it.each(["today", "soon"])("ledger?due=%s lands on the filtered ledger", async (due) => {
    mount(<Ledger makerspace={makerspace} isSuperadmin={false} />, `/?due=${due}`);
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("/ledger?") && String(path).includes(`due=${due}`))).toBe(true));
    expect((await screen.findByLabelText("Due") as HTMLSelectElement).value).toBe(due);
  });

  it("ignores an unknown ledger due window", async () => {
    mount(<Ledger makerspace={makerspace} isSuperadmin={false} />, "/?due=bogus");
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(staffRequest.mock.calls.every(([path]) => !String(path).includes("due="))).toBe(true);
  });

  it("machines?job=<id> opens that job", async () => {
    staffRequest.mockResolvedValue({ id: 31, title: "Bracket print", status: "pending", machine_type: "3D printer" });
    mount(<LinkedJob jobId={31} />, "/?job=31");
    expect(await screen.findByText("Bracket print")).toBeVisible();
    expect(staffRequest.mock.calls[0][0]).toBe("/admin/machine-service/requests/31");
  });
});

describe("report areas (decision 247 naming)", () => {
  it("files people exports under People, incidents under Safety, donations under Donations", () => {
    expect(reportArea("roster-export")).toBe("People");
    expect(reportArea("volunteer-hours-export")).toBe("People");
    expect(reportArea("minors-consent-export")).toBe("People");
    expect(reportArea("incidents-register")).toBe("Safety");
    expect(reportArea("machine-jobs")).toBe("Machines & service");
    expect(reportArea("certification-holders")).toBe("Machines & service");
    expect(reportArea("donations-pledges")).toBe("Donations");
    expect(reportArea("inventory-valuation")).toBe("Inventory");
    expect(reportAreaGroups([{ key: "roster-export" } as never]).map(([area]) => area)).toEqual(["People"]);
  });
});
