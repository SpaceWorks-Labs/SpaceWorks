import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MembersPanel } from "../staff/MembersPanel";

const api = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: api.staffRequest }));

const page = { count: 0, next: null, previous: null, results: [] };
const renderPanel = (presenceEnabled: boolean) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter initialEntries={["/admin/members?section=presence"]}>
    <MembersPanel makerspaceId={5} membershipEnabled presenceEnabled={presenceEnabled} actorActions={[]} isSuperadmin={false} onAuthRefresh={() => undefined} />
  </MemoryRouter></QueryClientProvider>);
const presenceCalls = () => api.staffRequest.mock.calls.filter(([path]) => String(path).includes("presence-sessions"));

beforeEach(() => {
  api.staffRequest.mockReset();
  api.staffRequest.mockImplementation(async (path: string) => (String(path).endsWith("/roles") ? [] : page));
});

describe("presence module gate in the staff Members panel", () => {
  it("module off: no Present-now tab, no presence stat, no presence request", async () => {
    renderPanel(false);
    await waitFor(() => expect(api.staffRequest).toHaveBeenCalled());
    expect(screen.queryByText("Present now")).not.toBeInTheDocument();
    expect(screen.queryByText("Currently present")).not.toBeInTheDocument();
    expect(presenceCalls()).toHaveLength(0);
  });

  it("module on: the Present-now tab reads the paginated roster", async () => {
    renderPanel(true);
    expect(await screen.findByRole("button", { name: "Check someone in" })).toBeInTheDocument();
    expect(screen.getAllByText("Present now").length).toBeGreaterThan(0);
    expect(presenceCalls().map(([path]) => path)).toContain("/admin/makerspace/5/presence-sessions/current?page=1");
  });
});
