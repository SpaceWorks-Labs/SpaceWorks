import { setRouteSessionContext } from "../../lib/api/sessionContext";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import { SetupChecklist } from "./SetupChecklist";
import { setupSteps, type SetupState } from "./setupChecklistState";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
vi.mock("./firstRun/FirstRunWizard", () => ({
  FirstRunWizard: ({ onClose }: { onClose: () => void }) => <div role="dialog" aria-label="Guided setup"><button type="button" onClick={onClose}>Close wizard</button></div>,
}));
const state: SetupState = { profile_set: false, hours_set: false, first_item_added: false, staff_invited: false, modules_chosen: false };
const space = { id: 7, name: "Forge", slug: "forge", public_code: "FORG", telegram_group_chat_id: "", frontend_domain: null, hidden_from_central_directory: false, enabled_modules: ["public_inventory"] };
function mount(id = 7) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><SetupChecklist key={id} makerspace={{ ...space, id }} owner="manager" allowedTabs={["inventory", "settings", "users"]} guestOnly={false} singleTenantLocked={false} /></MemoryRouter></QueryClientProvider>);
}
const started = (id = 7) => localStorage.setItem(`spaceworks.setup.wizard:manager:${id}`, JSON.stringify({ step: 1, finished: false, started: true }));
beforeEach(() => {
  setRouteSessionContext("person"); localStorage.clear(); staffRequest.mockReset(); staffRequest.mockResolvedValue(state);
  started(7); started(8);
});
it("derives completion from real state and omits inventory when its module is off", () => {
  expect(setupSteps({ ...state, hours_set: true }, []).map(step => [step.key, step.complete])).toEqual([["profile_set", false], ["hours_set", true], ["staff_invited", false], ["modules_chosen", false]]);
});
it("adds the logo step when the server reports logo progress", () => {
  expect(setupSteps({ ...state, logo_set: true }, []).map(step => [step.key, step.complete])).toEqual([["profile_set", false], ["logo_set", true], ["hours_set", false], ["staff_invited", false], ["modules_chosen", false]]);
});
it("links permitted setup actions and shows an administrator hint for forbidden modules", async () => {
  mount();
  fireEvent.click(await screen.findByText("All setup steps"));
  expect(await screen.findByRole("link", { name: "Add your first item" })).toHaveAttribute("href", "/m/forge/admin/inventory");
  expect(screen.getByText("Choose what your space runs · ask an administrator")).toBeVisible();
  expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
});
it("dismisses per makerspace and keeps another makerspace visible", async () => {
  const first = mount(); fireEvent.click(await screen.findByText("All setup steps")); await screen.findByRole("link", { name: "Set opening hours" });
  const hide = screen.getByRole("button", { name: "Hide setup checklist" });
  expect(hide).toHaveTextContent("Hide");
  fireEvent.click(hide); first.unmount();
  const again = mount(); expect(screen.queryByRole("heading", { name: /Next steps for Forge/ })).not.toBeInTheDocument(); again.unmount();
  mount(8); fireEvent.click(await screen.findByText("All setup steps")); expect(await screen.findByRole("link", { name: "Set opening hours" })).toBeVisible();
});
it("hides a completed checklist", async () => {
  staffRequest.mockResolvedValue(Object.fromEntries([...Object.keys(state), "logo_set"].map(key => [key, true])));
  mount();
  await vi.waitFor(() => expect(screen.queryByRole("heading", { name: /Next steps for Forge/ })).not.toBeInTheDocument());
});
it("shows real completion, the next permitted step and an expandable full list", async () => {
  staffRequest.mockResolvedValue({ ...state, profile_set: true, staff_invited: true });
  mount();
  expect(await screen.findByRole("heading", { name: "Next steps for Forge — 2 of 5 done" })).toBeVisible();
  expect(screen.getByRole("progressbar", { name: "Makerspace setup" })).toHaveAttribute("aria-valuenow", "40");
  expect(screen.getByRole("link", { name: "Set opening hours →" })).toHaveAttribute("href", "/m/forge/admin/settings/general");
  expect(screen.queryByRole("link", { name: "Add your first item" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("All setup steps"));
  expect(screen.getByRole("link", { name: "Add your first item" })).toBeVisible();
});
it("opens the guided setup by itself once for a brand-new space, then waits for the button", async () => {
  localStorage.clear();
  staffRequest.mockResolvedValue({ ...state, logo_set: false });
  const first = mount();
  expect(await screen.findByRole("dialog", { name: "Guided setup" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close wizard" }));
  expect(screen.queryByRole("dialog", { name: "Guided setup" })).not.toBeInTheDocument();
  first.unmount();
  // The real wizard records that it started; mimic that so a remount does not reopen it.
  started();
  mount();
  expect(await screen.findByRole("button", { name: "Continue guided setup" })).toBeVisible();
  expect(screen.queryByRole("dialog", { name: "Guided setup" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Continue guided setup" }));
  expect(screen.getByRole("dialog", { name: "Guided setup" })).toBeVisible();
});
it("does not open the guided setup by itself once something is set up", async () => {
  localStorage.clear();
  staffRequest.mockResolvedValue({ ...state, hours_set: true });
  mount();
  expect(await screen.findByRole("button", { name: "Start guided setup" })).toBeVisible();
  expect(screen.queryByRole("dialog", { name: "Guided setup" })).not.toBeInTheDocument();
});
