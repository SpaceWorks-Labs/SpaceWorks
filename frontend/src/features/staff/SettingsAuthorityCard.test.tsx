import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { SettingsAuthorityCard } from "./SettingsAuthorityCard";
import type { GrantsResponse } from "./settingsAuthorityApi";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));

const data: GrantsResponse = {
  grants: [{ id: 3, module: "events", grantee: 11, grantee_name: "Esha Events", grantee_email: "e@x.test",
    granted_at: "2026-10-29T00:00:00Z" }],
  candidates: {
    events: [{ id: 11, name: "Esha Events", email: "e@x.test" }],
    bookings: [], machines: [{ id: 12, name: "Milo Machines", email: "m@x.test" }], inventory: [],
  },
};
const path = "/admin/makerspace/7/settings-authority/grants";

beforeEach(() => {
  vi.mocked(staffRequest).mockReset();
  vi.mocked(staffRequest).mockResolvedValue(data as never);
});

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><SettingsAuthorityCard makerspaceId={7} /></QueryClientProvider>);
}

it("lists each module's grant holders and says who can change the rest", async () => {
  mount();
  expect(await screen.findByRole("heading", { name: "Who can change settings" })).toBeInTheDocument();
  expect(screen.getByText("Esha Events")).toBeInTheDocument();
  expect(screen.getAllByText("Only you can change these.")).toHaveLength(3);
  expect(screen.getByText(/Inventory Managers always set loan length and renewals/)).toBeInTheDocument();
});

it("gives one person control of a module's settings", async () => {
  mount();
  const select = await screen.findByRole("combobox", { name: "Give control to" });
  fireEvent.change(select, { target: { value: "12" } });
  const row = select.closest("li") as HTMLElement;
  fireEvent.click(within(row).getByRole("button", { name: "Give control" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(path, {
    method: "PUT", body: JSON.stringify({ module: "machines", grantee_ids: [12] }),
  }));
});

it("removes a person's grant, keeping the others", async () => {
  mount();
  fireEvent.click(await screen.findByRole("button", { name: /^Remove Esha Events/ }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(path, {
    method: "PUT", body: JSON.stringify({ module: "events", grantee_ids: [] }),
  }));
});
