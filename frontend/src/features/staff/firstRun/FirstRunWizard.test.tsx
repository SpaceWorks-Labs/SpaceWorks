import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { FirstRunWizard } from "./FirstRunWizard";
import { readWizardProgress } from "./firstRunWizardState";
import type { SetupState } from "../setupChecklistState";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async importOriginal => ({ ...await importOriginal<object>(), staffRequest }));
vi.mock("../ImageUploader", () => ({ ImageUploader: ({ label }: { label: string }) => <p>{`${label} uploader`}</p> }));
vi.mock("../StaffTabLoaders", () => ({ ModulesPanel: ({ makerspaceId }: { makerspaceId: number }) => <p>{`Areas for ${makerspaceId}`}</p> }));

const space = { id: 7, name: "Forge", slug: "forge", public_code: "FORG", telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false };
const none: SetupState = { profile_set: false, logo_set: false, hours_set: false, first_item_added: false, staff_invited: false, modules_chosen: false };
const profile = { timezone: "Europe/Berlin", country: "", default_currency: "eur", opening_hours: {}, timezone_choices: ["Europe/Berlin"], country_choices: [] };
const policy = { grantable_roles: [{ slug: "inventory_manager", name: "Inventory Manager", combinable: true }], can_manage_space_managers: false, email_invites_available: true, machine_types: [] };

function mount(state: SetupState = none, onClose = vi.fn()) {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <FirstRunWizard makerspace={space} owner="manager" state={state} onClose={onClose} />
  </QueryClientProvider>);
  return onClose;
}

beforeEach(() => {
  localStorage.clear();
  staffRequest.mockReset();
  staffRequest.mockImplementation((path: string, init?: RequestInit) => {
    if (path.endsWith("/profile")) return Promise.resolve(init?.method === "PATCH" ? { ...profile, opening_hours: JSON.parse(String(init.body)).opening_hours } : profile);
    if (path.includes("/staff-roles/")) return Promise.resolve(init?.method === "POST" ? { kind: "invited", staff_role: null, invitation_id: 3, delivery_status: "sent" } : { count: 0, next: null, previous: null, results: [], policy });
    return Promise.resolve({});
  });
});

it("walks every step, lets each be skipped and remembers where you stopped", async () => {
  const onClose = mount();
  expect(screen.getByRole("heading", { name: "Name your space" })).toBeVisible();
  expect(screen.getByRole("progressbar", { name: "Step 1 of 5" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Back" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
  expect(screen.getByRole("heading", { name: "Add your logo" })).toBeVisible();
  expect(screen.getByText("Logo uploader")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
  expect(await screen.findByRole("heading", { name: "Set your opening hours" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Skip for now" }));
  expect(await screen.findByText("Areas for 7")).toBeVisible();
  expect(readWizardProgress("manager", 7)).toEqual({ step: 3, finished: false, started: true });
  fireEvent.click(screen.getAllByRole("button", { name: "Close dialog" })[0]);
  expect(onClose).toHaveBeenCalled();
});

it("resumes at the saved step after closing and reopening", async () => {
  localStorage.setItem("spaceworks.setup.wizard:manager:7", JSON.stringify({ step: 4, finished: false, started: true }));
  const onClose = mount();
  expect(screen.getByRole("heading", { name: "Invite your staff" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Skip for now" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Finish" }));
  expect(onClose).toHaveBeenCalled();
  expect(readWizardProgress("manager", 7)).toMatchObject({ finished: true, started: true });
});

it("saves the space name through the makerspace endpoint and moves on", async () => {
  mount();
  fireEvent.change(screen.getByRole("textbox", { name: /Space name/ }), { target: { value: "Forge Lab" } });
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7", { method: "PATCH", body: JSON.stringify({ name: "Forge Lab" }) }));
  expect(await screen.findByRole("heading", { name: "Add your logo" })).toBeVisible();
});

it("starts hours from a weekday week and saves them to the profile", async () => {
  localStorage.setItem("spaceworks.setup.wizard:manager:7", JSON.stringify({ step: 2, finished: false, started: true }));
  mount();
  expect(await screen.findByText("Times use Europe/Berlin. Change the timezone in Settings › Profile & location.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Save and continue" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspace/7/profile", expect.objectContaining({ method: "PATCH" })));
  const body = JSON.parse(String(staffRequest.mock.calls.find(([path, init]) => path.endsWith("/profile") && init?.method === "PATCH")![1].body));
  expect(body.opening_hours.weekly.mon).toEqual([{ start: "09:00", end: "17:00" }]);
  expect(body.opening_hours.weekly.sat).toEqual([]);
  expect(await screen.findByText("Areas for 7")).toBeVisible();
});

it("invites staff by email with a role and says whether the email went out", async () => {
  localStorage.setItem("spaceworks.setup.wizard:manager:7", JSON.stringify({ step: 4, finished: false, started: true }));
  mount();
  fireEvent.change(await screen.findByRole("textbox", { name: /Their email/ }), { target: { value: "ada@example.org" } });
  fireEvent.click(screen.getByRole("checkbox", { name: /Inventory Manager/ }));
  fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7/staff-roles/", {
    method: "POST", body: JSON.stringify({ email: "ada@example.org", roles: ["inventory_manager"], machine_type_ids: [], machine_ids: [] }),
  }));
  expect(await screen.findByText("Invitation email sent.")).toBeVisible();
  expect(screen.getByText("Invited so far: ada@example.org")).toBeVisible();
});

it("explains when email is not set up instead of offering an invite that cannot be sent", async () => {
  localStorage.setItem("spaceworks.setup.wizard:manager:7", JSON.stringify({ step: 4, finished: false, started: true }));
  staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [], policy: { ...policy, email_invites_available: false } });
  mount();
  expect(await screen.findByText(/Email is not set up on this server yet/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Send invitation" })).not.toBeInTheDocument();
});

it("marks a step the server already reports as done", () => {
  localStorage.setItem("spaceworks.setup.wizard:manager:7", JSON.stringify({ step: 1, finished: false, started: true }));
  mount({ ...none, logo_set: true });
  expect(screen.getByText("Done")).toBeVisible();
});
