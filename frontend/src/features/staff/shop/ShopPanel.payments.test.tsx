import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShopPanel } from "./ShopPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async () => ({ ...(await vi.importActual<object>("../../../lib/api")), staffRequest }));

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string) => path.includes("summary") ? { groups: [] }
    : { count: 0, next: null, previous: null, results: [] });
});

function mount(actions: string[], path = "/admin/shop") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={[path]}><QueryClientProvider client={client}>
    <ShopPanel makerspace={{ id: 4, name: "Lab", slug: "lab", enabled_modules: ["shop"], enabled_features: [] } as never}
      actions={actions} isSuperadmin={false} />
  </QueryClientProvider></MemoryRouter>);
}

describe("Shop console Payments tab (decision 242 a)", () => {
  it("lists a Payments section for the Shop Manager, reading only shop charges", async () => {
    mount(["manage_shop", "sell_shop", "view_shop"], "/admin/shop/payments");
    expect(screen.getByRole("tab", { name: "Payments" })).toBeVisible();
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("area-queue?area=shop"))).toBe(true));
  });

  it("keeps Payments out of a seller's view (no shop money authority)", () => {
    mount(["sell_shop", "view_shop"]);
    expect(screen.queryByRole("tab", { name: "Payments" })).toBeNull();
  });
});
