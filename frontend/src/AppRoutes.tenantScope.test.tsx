import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { AppRoutes } from "./AppRoutes";
import { StructuredApiError } from "./lib/api/errors";

vi.mock("./AppRoutesLazyPages", async (original) => ({
  ...await original<typeof import("./AppRoutesLazyPages")>(),
  AccountRestorePage: () => <p>Account restore route</p>,
  ProgrammeRoutes: () => <p>Personal account utility route</p>,
}));

it.each(["single", "central"] as const)("renders global account restoration in %s mode without the tenant query context", (mode) => {
  render(<MemoryRouter initialEntries={["/account/restore"]}><AppRoutes mode={mode} landing={null} /></MemoryRouter>);
  expect(screen.getByText("Account restore route")).toBeInTheDocument();
});

async function renderWithPausedTenant(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  await client.fetchQuery({
    queryKey: ["tenant-bootstrap", "north-lab"],
    queryFn: async () => { throw new StructuredApiError(404, { detail: "Not found." }); },
  }).catch(() => undefined);
  client.setQueryData(["public-space-availability", "north-lab"], { state: "paused" });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <AppRoutes mode="central" landing={null} />
  </MemoryRouter></QueryClientProvider>);
}

it.each(["saved-details", "security-activity"])("opens %s despite the paused tenant's cached bootstrap error", async (page) => {
  await renderWithPausedTenant(`/m/north-lab/member/account/${page}`);
  expect(screen.getByText("Personal account utility route")).toBeInTheDocument();
  expect(screen.queryByText("This space is paused")).not.toBeInTheDocument();
});

it("still shows the paused page on a normal tenant route", async () => {
  await renderWithPausedTenant("/m/north-lab/events");
  expect(screen.getByText("This space is paused")).toBeInTheDocument();
});
