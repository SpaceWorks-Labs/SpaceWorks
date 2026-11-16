import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../lib/api";
import { EventDefaultsSettings } from "./EventDefaultsSettings";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));
const feature = "events.organization_audience";
const audience = "participating_organizations";
const path = "/admin/makerspaces/7";
const key = ["makerspace-settings", 7];
const settings = { event_default_registration_audience: "members", enabled_features: [feature] };

beforeEach(() => {
  vi.mocked(staffRequest).mockReset();
  vi.mocked(staffRequest).mockResolvedValue(settings);
});

async function mount() {
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false, staleTime: Infinity }, mutations: { retry: false },
  } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><EventDefaultsSettings makerspaceId={7} /></QueryClientProvider>);
  const select = screen.getByRole("combobox", { name: "Default registration audience" });
  await waitFor(() => expect(select).toBeEnabled());
  expect(staffRequest).toHaveBeenCalledWith(path);
  return { client, invalidate, select };
}

it("saves the organization default and refreshes settings and event server state", async () => {
  const { client, invalidate, select } = await mount();
  expect(screen.getByRole("option", { name: "Selected organizations" })).toBeEnabled();
  const saved = { ...settings, event_default_registration_audience: audience };
  vi.mocked(staffRequest).mockResolvedValue(saved);
  fireEvent.change(select, { target: { value: audience } });
  fireEvent.click(screen.getByRole("button", { name: "Save event defaults" }));
  expect(await screen.findByRole("status")).toHaveTextContent("Event defaults saved.");
  expect(staffRequest).toHaveBeenCalledWith(path, {
    method: "PATCH", body: JSON.stringify({ event_default_registration_audience: audience }),
  });
  expect(client.getQueryData(key)).toEqual(saved);
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["staff", "makerspaces"] });
  expect(invalidate).toHaveBeenCalledWith({ queryKey: ["events", 7] });
  expect(select).toHaveValue(audience);
  expect(screen.getByRole("button", { name: "Save event defaults" })).toBeDisabled();
});

it("omits the organization option when its feature is off and keeps existing audiences", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ ...settings, enabled_features: [] });
  const { select } = await mount();
  expect(select).toHaveValue("members");
  expect(screen.queryByRole("option", { name: "Selected organizations" })).toBeNull();
  expect(screen.getAllByRole("option").map((option) => option.getAttribute("value")))
    .toEqual(["accounts", "members", "invite"]);
});

it.each([true, false])("displays an API-saved organization default with feature enabled=%s", async (enabled) => {
  vi.mocked(staffRequest).mockResolvedValue({
    ...settings, event_default_registration_audience: audience, enabled_features: enabled ? [feature] : [],
  });
  const { select } = await mount();
  expect(select).toHaveValue(audience);
  const option = screen.getByRole("option", { name: "Selected organizations" });
  if (enabled) expect(option).toBeEnabled();
  else {
    expect(option).toBeDisabled();
    expect(screen.getByText(/Enable the Participating organizations audience in Features/)).toBeVisible();
    // Staff can replace the unavailable default with an existing audience.
    fireEvent.change(select, { target: { value: "members" } });
    expect(screen.getByRole("button", { name: "Save event defaults" })).toBeEnabled();
    expect(screen.queryByRole("option", { name: "Selected organizations" })).toBeNull();
  }
});

it("blocks saving an organization draft if a feature refresh disables it", async () => {
  const { client, select } = await mount();
  fireEvent.change(select, { target: { value: audience } });
  await act(async () => { client.setQueryData(key, { ...settings, enabled_features: [] }); });
  await waitFor(() => expect(screen.getByRole("button", { name: "Save event defaults" })).toBeDisabled());
  expect(select).toHaveValue(audience);
  expect(screen.getByRole("option", { name: "Selected organizations" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Save event defaults" }));
  expect(staffRequest).toHaveBeenCalledTimes(1);
});

it("keeps the draft and shows the API error when saving fails", async () => {
  const { client, select } = await mount();
  vi.mocked(staffRequest).mockRejectedValue(new Error("Enable organization audience first."));
  fireEvent.change(select, { target: { value: audience } });
  fireEvent.click(screen.getByRole("button", { name: "Save event defaults" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Enable organization audience first.");
  expect(select).toHaveValue(audience);
  expect(client.getQueryData(key)).toEqual(settings);
  expect(screen.getByRole("button", { name: "Save event defaults" })).toBeEnabled();
});
