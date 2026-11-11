import { afterEach, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProgrammeTeamsPanel } from "./ProgrammeTeamsPanel";
import { staffRequest } from "../../../lib/api";
vi.mock("../../../lib/api", () => ({ staffRequest: vi.fn(), memberRequest: vi.fn() }));
vi.mock("./sessionScope", () => ({ sessionScope: () => ["actor-17"] }));
afterEach(() => vi.clearAllMocks());
it("loads scoped teams/projects and sends versioned review to its actual route", async () => {
  vi.mocked(staffRequest).mockImplementation(async (path) => {
    if (String(path).includes("/triage/")) return { id: 5, event_id: 42, version: 4, state: "locked" } as never;
    if (String(path).includes("/submissions/")) return { count: 1, next: null, previous: null, results: [{ id: 5, team_name: "Copper", title: "Sensor", state: "locked", version: 3, triage: "pending", allowed_actions: ["triage"], assets: [] }] } as never;
    return { count: 1, next: null, previous: null, results: [{ id: 7, name: "Copper", state: "locked", version: 2, member_count: 3, eligibility_issue: false }] } as never;
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ProgrammeTeamsPanel eventId={42} canTriage /></QueryClientProvider>);
  expect(await screen.findByText("Sensor · Copper")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Meets the submission policy." } });
  fireEvent.click(screen.getByText("Save project review"));
  await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([path, init]) => String(path).includes("/triage/") && JSON.parse(String(init?.body)).expected_version === 3)).toBe(true));
  client.clear();
});
