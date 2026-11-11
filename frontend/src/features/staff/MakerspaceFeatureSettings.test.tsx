import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { staffRequest } from "../../lib/api";
import { MakerspaceFeatureSettings } from "./MakerspaceFeatureSettings";
import type { Makerspace } from "./panels/shared";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));
const feature = "events.organization_audience";
const makerspace = { id: 7, name: "Venue", slug: "venue", enabled_modules: ["events"],
  enabled_features: ["events.invites"] } as Makerspace;

beforeEach(() => { vi.mocked(staffRequest).mockReset(); vi.mocked(staffRequest).mockResolvedValue(makerspace); });

function mount(settings = makerspace) {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}>
    <MakerspaceFeatureSettings makerspace={makerspace} settings={settings} loading={false} />
  </QueryClientProvider>);
  return invalidate;
}

it("lets staff enable organization audiences while preserving other features and refreshing settings", async () => {
  const invalidate = mount();
  const toggle = screen.getByRole("checkbox", { name: "Participating organizations audience" });
  expect(toggle).toBeEnabled();
  expect(toggle).not.toBeChecked();
  fireEvent.click(toggle);
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7", {
    method: "PATCH", body: JSON.stringify({ enabled_features: ["events.invites", feature] }),
  }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["makerspace-settings", 7] }));
});

it("gates the organization-audience toggle on the events module", () => {
  mount({ ...makerspace, enabled_modules: [] });
  const toggle = screen.getByRole("checkbox", { name: "Participating organizations audience" });
  expect(toggle).toBeDisabled();
  fireEvent.click(toggle);
  expect(staffRequest).not.toHaveBeenCalled();
});

it("explains each switch in one plain line and never shows raw module keys (decision 235)", () => {
  mount({ ...makerspace, enabled_modules: ["events", "public_inventory"] });
  const toggle = screen.getByRole("checkbox", { name: "Participating organizations audience" });
  expect(toggle).toHaveAccessibleDescription("Limit registration to members of the organising organisation.");
  expect(screen.getAllByText("Public inventory").length).toBeGreaterThan(0);
  expect(screen.queryByText("public_inventory")).not.toBeInTheDocument();
});
