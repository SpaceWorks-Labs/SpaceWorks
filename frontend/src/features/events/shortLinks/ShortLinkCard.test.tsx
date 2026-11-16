import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { staffRequest, StructuredApiError } from "../../../lib/api";
import { ShortLinkCard } from "./ShortLinkCard";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const days = Array.from({ length: 30 }, (_, index) => ({ day: `2026-10-${String(index + 1).padStart(2, "0")}`, count: index === 29 ? 4 : 0 }));
const live = { code: "AbC1234", url: "https://space.example/e/AbC1234", created_at: "2026-10-29T10:00:00Z", visits_30d: days, total_visits: 9 };

beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

function mount(published = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><ShortLinkCard eventId={5} published={published} /></QueryClientProvider>);
}

it("creates a link on request and shows visits as a decorative sparkline with a text total", async () => {
  vi.mocked(staffRequest).mockImplementation(async (_url: string, options?: RequestInit) =>
    (options?.method === "POST" ? live : { ...live, code: null, url: null, created_at: null, total_visits: 0 }) as never);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Create short link" }));
  expect(await screen.findByRole("link", { name: live.url })).toBeInTheDocument();
  expect(vi.mocked(staffRequest)).toHaveBeenCalledWith("/admin/events/5/short-link/", { method: "POST" });
  expect(screen.getByText(/visits in the last 30 days/)).toHaveTextContent("4 visits in the last 30 days · 9 in total");
  expect(screen.getByText("Visits are counted without storing who visited.")).toBeInTheDocument();
});

it("asks before regenerating because the old link stops working", async () => {
  vi.mocked(staffRequest).mockImplementation(async (url: string) =>
    (url.endsWith("regenerate/") ? { ...live, code: "Zz99999", url: "https://space.example/e/Zz99999" } : live) as never);
  mount();
  fireEvent.click(await screen.findByRole("button", { name: "Make a new link" }));
  expect(screen.getByText("The old link stops working straight away.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Make new link" }));
  await waitFor(() => expect(vi.mocked(staffRequest)).toHaveBeenCalledWith("/admin/events/5/short-link/regenerate/",
    { method: "POST", body: JSON.stringify({ confirm: true }) }));
  expect(await screen.findByRole("link", { name: "https://space.example/e/Zz99999" })).toBeInTheDocument();
});

it("offers nothing before publishing and disappears when short links are off", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ ...live, code: null, url: null } as never);
  mount(false);
  expect(await screen.findByRole("button", { name: "Create short link" })).toBeDisabled();
});

it("renders nothing while the space has short links switched off", async () => {
  vi.mocked(staffRequest).mockRejectedValue(new StructuredApiError(404, { detail: "off" }));
  const { container } = render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <ShortLinkCard eventId={5} published /></QueryClientProvider>);
  await waitFor(() => expect(container).toBeEmptyDOMElement());
});
