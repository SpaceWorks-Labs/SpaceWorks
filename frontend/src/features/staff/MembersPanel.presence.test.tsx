import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { MembersPanel } from "./MembersPanel";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), staffRequest }));
const empty = { count: 0, results: [], next: null, previous: null };

function show(id = 3, presenceEnabled = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter initialEntries={["/admin/members?section=presence"]}><QueryClientProvider client={client}>
    <MembersPanel makerspaceId={id} membershipEnabled={false} presenceEnabled={presenceEnabled}
      actorActions={["manage_members"]} isSuperadmin={false} onAuthRefresh={() => {}} />
  </QueryClientProvider></MemoryRouter>);
}

beforeEach(() => {
  staffRequest.mockReset().mockImplementation(async (path: string) => {
    if (/^\/admin\/makerspaces\/\d+$/.test(path)) return { presence_preset_minutes: [15, 30] };
    if (path.endsWith("/roles")) return [];
    if (path.includes("q=ada")) return { ...empty, results: [{ id: 4, user: { id: 9, username: "ada", display_name: "Ada" } }] };
    return empty;
  });
});

it("passes configured durations through the roster and posts the selected staff check-in", async () => {
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Check someone in" }));
  const dialog = screen.getByRole("dialog", { name: "Check someone in" });
  const durations = within(dialog).getByRole("radiogroup", { name: "Duration" });
  expect(within(durations).getAllByRole("radio").map(row => row.textContent)).toEqual(["15 min", "30 min"]);
  fireEvent.click(within(durations).getByRole("radio", { name: "30 min" }));
  fireEvent.change(within(dialog).getByLabelText("Find a member or guest"), { target: { value: "ada" } });
  fireEvent.click(await within(dialog).findByRole("radio", { name: /Ada/ }));
  fireEvent.click(within(dialog).getByRole("button", { name: /^Check in$/ }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/3/presence-sessions/check-in",
    { method: "POST", body: JSON.stringify({ account_id: 9, duration_minutes: 30 }) }));
});

it("waits for tenant policy before offering check-in", async () => {
  let resolve!: (value: unknown) => void;
  const normal = staffRequest.getMockImplementation()!;
  staffRequest.mockImplementation((path: string) => path === "/admin/makerspaces/3"
    ? new Promise(done => { resolve = done; }) : normal(path));
  show();
  expect(await screen.findByText("Loading check-in durations…")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Check someone in" })).toBeNull();
  resolve({ presence_preset_minutes: [15, 30] });
  expect(await screen.findByRole("button", { name: "Check someone in" })).toBeVisible();
});

it("uses the shared defaults only for an unconfigured tenant", async () => {
  const normal = staffRequest.getMockImplementation()!;
  staffRequest.mockImplementation((path: string) => path === "/admin/makerspaces/3"
    ? Promise.resolve({ presence_preset_minutes: [] }) : normal(path));
  show();
  fireEvent.click(await screen.findByRole("button", { name: "Check someone in" }));
  expect(within(screen.getByRole("radiogroup", { name: "Duration" })).getAllByRole("radio").map(row => row.textContent))
    .toEqual(["1 h", "2 h", "3 h", "4 h"]);
});

it("offers a retry after a policy failure and keeps check-in unavailable until recovery", async () => {
  const normal = staffRequest.getMockImplementation()!;
  let failing = true;
  staffRequest.mockImplementation((path: string) => path === "/admin/makerspaces/3" && failing
    ? Promise.reject(new Error("Unavailable")) : normal(path));
  show();
  expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load check-in durations");
  expect(screen.queryByRole("button", { name: "Check someone in" })).toBeNull();
  failing = false;
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("button", { name: "Check someone in" })).toBeVisible();
});

it("does not fetch presence policy when the module is off", async () => {
  show(3, false);
  await waitFor(() => expect(staffRequest).toHaveBeenCalled());
  expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspaces/3");
});
