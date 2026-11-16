import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Makerspace } from "./panels/shared";
import { SettingsHub } from "./SettingsHub";
import { searchHub, hubEntries, setupChecklist } from "./settingsHubCatalog";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest, memberRequest: vi.fn(), getAccessToken: () => null }));

const SECTIONS = ["start", "general", "branding", "features", "lending", "membership", "money", "notifications", "channels", "integrations", "privacy"];
const space = (overrides: Partial<Makerspace> = {}) => ({ id: 4, name: "Lab", slug: "lab", public_code: "LAB", telegram_group_chat_id: "",
  frontend_domain: null, hidden_from_central_directory: false, enabled_modules: ["notifications", "membership"], enabled_features: [], ...overrides }) as Makerspace;

function mount(makerspace = space(), allowedTabs = ["users", "api", "exports", "inventory"]) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>
    <SettingsHub makerspace={makerspace} sectionIds={SECTIONS} allowedTabs={allowedTabs} tabHref={tab => `/m/lab/admin/${tab}`} />
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] }); });

describe("settings hub search", () => {
  it("matches every word against titles, descriptions and keywords", () => {
    const entries = hubEntries(SECTIONS, ["users"]);
    expect(searchHub(entries, "whatsapp").map(entry => entry.id)).toEqual(["channels"]);
    expect(searchHub(entries, "loan days").map(entry => entry.id)).toEqual(["lending"]);
    expect(searchHub(entries, "appoint staff").map(entry => entry.id)).toEqual(["tab:users"]);
    expect(searchHub(entries, "   ")).toEqual([]);
  });

  it("offers only sections on the page and tabs the actor may open", () => {
    const ids = hubEntries(["general"], ["api"]).map(entry => entry.id);
    expect(ids).toEqual(["general", "tab:api"]);
  });

  it("filters as you type and jumps to an on-page section", () => {
    mount();
    const target = document.createElement("div");
    target.id = "channels"; target.tabIndex = -1; target.scrollIntoView = vi.fn();
    document.body.appendChild(target);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search settings" }), { target: { value: "telegram" } });
    const results = within(screen.getByRole("region", { name: "Search results" }));
    fireEvent.click(results.getByRole("link", { name: /Communication channels/ }));
    expect(target.scrollIntoView).toHaveBeenCalledWith({ block: "start" });
    target.remove();
  });

  it("links tab destinations through the router and says when nothing matches", () => {
    mount();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search settings" }), { target: { value: "export" } });
    expect(screen.getByRole("link", { name: /Data export/ })).toHaveAttribute("href", "/m/lab/admin/exports");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search settings" }), { target: { value: "zzzz" } });
    expect(screen.getByText("No settings match. Try another word.")).toBeInTheDocument();
  });
});

describe("setup checklist and Staff & roles", () => {
  it("derives done states from the space and the channel settings", async () => {
    staffRequest.mockResolvedValue({ count: 1, next: null, previous: null, results: [{ channel: "telegram", enabled: true }] });
    mount(space({ location: "12 Forge St", logo_url: null }));
    const checklist = within(screen.getByRole("region", { name: "Setup checklist" }));
    expect(checklist.getByRole("link", { name: /Add your address: done/ })).toBeInTheDocument();
    expect(checklist.getByRole("link", { name: /Upload your logo: to do/ })).toBeInTheDocument();
    await waitFor(() => expect(checklist.getByRole("link", { name: /Choose how people get notified: done/ })).toBeInTheDocument());
    expect(staffRequest).toHaveBeenCalledWith("/integrations/makerspace/4/channels");
  });

  it("keeps channel setup independent of the notifications inbox module", () => {
    const items = setupChecklist(space({ enabled_modules: [] }), { channelsReady: true });
    expect(items.map(item => item.id)).toEqual(["location", "logo", "support", "features", "channels"]);
    mount(space({ enabled_modules: [] }));
    expect(staffRequest).toHaveBeenCalledWith("/integrations/makerspace/4/channels");
  });

  it("puts Staff & roles at the top for those who may appoint staff", () => {
    mount();
    expect(screen.getByRole("link", { name: /Staff & roles/ })).toHaveAttribute("href", "/m/lab/admin/users");
    expect(within(screen.getByRole("region", { name: "More settings pages" })).getByRole("link", { name: /Inventory settings/ })).toBeInTheDocument();
  });

  it("hides Staff & roles from anyone without the tab", () => {
    mount(space(), ["api"]);
    expect(screen.queryByRole("link", { name: /Staff & roles/ })).toBeNull();
  });
});
