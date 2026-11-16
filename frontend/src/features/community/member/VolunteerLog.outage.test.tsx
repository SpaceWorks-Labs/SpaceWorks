import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { memberRequest, StructuredApiError } from "../../../lib/api";
import { communityKeys } from "../api";
import { VolunteerLog } from "./VolunteerLog";

vi.mock("../../../lib/api", async original => ({ ...(await original<typeof import("../../../lib/api")>()), memberRequest: vi.fn() }));
it("retries failed credits without refetching successfully loaded hours", async () => {
  const failure = new StructuredApiError(503, { code: "service_unavailable", detail: "Credits unavailable" });
  vi.mocked(memberRequest).mockReset().mockImplementation(async path => {
    if (path.endsWith("/volunteer-credits")) throw failure;
    return [];
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><VolunteerLog makerspaceId={3} /></QueryClientProvider>);
  expect(await screen.findByText("No hours logged yet.")).toBeVisible();
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  await waitFor(() => expect(vi.mocked(memberRequest).mock.calls.filter(([path]) => path.endsWith("/volunteer-credits"))).toHaveLength(2));
  expect(vi.mocked(memberRequest).mock.calls.filter(([path]) => path.endsWith("/volunteer-hours"))).toHaveLength(1);
  const error = client.getQueryState(communityKeys.myCredits(3))!.error as StructuredApiError;
  expect({ status: error.status, code: error.code }).toEqual({ status: 503, code: "service_unavailable" });
});
