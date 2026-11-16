import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()),
  staffRequest: request, staffRequestBlob: vi.fn(async () => new Blob()) }));
vi.mock("zxing-wasm/writer", () => ({ setZXingModuleOverrides: vi.fn(), writeBarcode: vi.fn(async () => ({ image: null })) }));
vi.mock("../../../components/card-designer/CardDesigner", () => ({ CardDesigner: () => <p>Free canvas designer</p> }));

import { defaultSettings } from "./badgeNormalize";
import { RoleBadgeTabs } from "./RoleBadgeTabs";

const settings = defaultSettings("Build Night", "Tinkerspace");
const designRow = { id: 41, revision: 2, can_edit: true, status: "draft", published_at: null, has_unpublished_changes: true,
  needs_approval: false, pending_approval: null, can_approve: false,
  document: { version: 2, source: { format: "badge_v1", settings }, front: { layers: [] }, back: { layers: [] } } };
const info = (roleBadges: boolean, roles: { role: string; design_id: number | null; format: string }[]) => ({
  event_id: 7, event_title: "Build Night", organisation_name: "Tinkerspace", role_badges: roleBadges,
  roles: roles.map((row) => ({ published: false, ...row })), fields: [{ key: "attendee:team", label: "Team" }],
  max_print_fields: 8, sponsor_limit_max: 6, presets: [{ id: "a6", width_mm: 105, height_mm: 148 }], templates: ["classic"],
  branding: { has_organisation_logo: false, has_event_logo: false, sponsor_count: 0 } });

function mount(data: ReturnType<typeof info>) {
  request.mockImplementation(async (path: string) => {
    if (path === "/admin/events/7/badge-designs") return data;
    if (path === "/admin/card-designs/41") return designRow;
    if (path === "/admin/events/7/badge-designs/crew") return { design: { ...designRow, id: 42 }, created: true };
    throw new Error(`Unexpected path ${path}`);
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><RoleBadgeTabs eventId={7} /></QueryClientProvider>);
}

beforeEach(() => { request.mockReset(); });

it("opens the attendee badge in the badge designer", async () => {
  mount(info(false, [{ role: "attendee", design_id: 41, format: "badge_v1" }]));
  expect(await screen.findByRole("heading", { name: "Badge designer" })).toBeInTheDocument();
  expect(screen.queryByRole("radiogroup", { name: "Badge for" })).toBeNull();
  expect(screen.getByRole("button", { name: "Publish badge" })).toBeEnabled();
});

it("a role without its own design falls back to the attendee design and can be given one", async () => {
  mount(info(true, [{ role: "attendee", design_id: 41, format: "badge_v1" }, { role: "crew", design_id: null, format: "none" }]));
  fireEvent.click(await screen.findByRole("radio", { name: "Crew" }));
  expect(screen.getByText("Crew badges use the attendee design, with their own label.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Give Crew badges their own design" }));
  await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/events/7/badge-designs/crew",
    expect.objectContaining({ method: "POST", body: JSON.stringify({ restart: false }) })));
});

it("hides role tabs when role badges are off, and opens a converted badge in the free-canvas designer", async () => {
  mount(info(false, [{ role: "attendee", design_id: 41, format: "free_canvas" }, { role: "crew", design_id: null, format: "none" }]));
  expect(await screen.findByText("Free canvas designer")).toBeInTheDocument();
  expect(screen.queryByRole("radio", { name: "Crew" })).toBeNull();
  expect(screen.getByRole("button", { name: "Start a badge designer design instead…" })).toBeInTheDocument();
});
