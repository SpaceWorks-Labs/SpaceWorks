import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ModuleDefaultsSection, PlatformAdminsSection } from "./PlatformDefaultsSections";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const mount = (ui: React.ReactElement) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{ui}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("feature defaults (open item C13)", () => {
  it("shows each feature's default and how many spaces use it", async () => {
    staffRequest.mockResolvedValue({ spaces_total: 3, modules: [
      { key: "inventory", label: "Inventory", description: "Items and borrowing.", group: "core", always_on: true, on_for_new_spaces: true, spaces_on: 3 },
      { key: "events", label: "Events", description: "Workshops.", group: "programme", always_on: false, on_for_new_spaces: false, spaces_on: 1 },
    ] });
    mount(<ModuleDefaultsSection />);
    expect(await screen.findByText("Always on")).toBeVisible();
    expect(screen.getByText("Off for new spaces")).toBeVisible();
    expect(screen.getByText("1 of 3 spaces")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/module-defaults", {}, "platform");
  });

  it("offers a retry when loading fails", async () => {
    staffRequest.mockImplementation(() => Promise.reject(new Error("down")));
    mount(<ModuleDefaultsSection />);
    expect(await screen.findByRole("button", { name: /try again|retry/i })).toBeVisible();
  });
});

describe("platform admins (open item C13)", () => {
  it("lists admins with status and two-step sign-in, no contact details", async () => {
    staffRequest.mockResolvedValue({ admins: [
      { id: 1, username: "root", is_active: true, mfa_enabled: false, last_login: null },
    ] });
    mount(<PlatformAdminsSection />);
    expect(await screen.findByText("root")).toBeVisible();
    expect(screen.getByText("Two-step off")).toBeVisible();
    expect(screen.getByText("Never signed in")).toBeVisible();
  });

  it("says so when the list is empty", async () => {
    staffRequest.mockResolvedValue({ admins: [] });
    mount(<PlatformAdminsSection />);
    expect(await screen.findByText("No platform admins found.")).toBeVisible();
  });
});
