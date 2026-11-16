import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api/errors";
import { GalleryPage } from "./GalleryPage";

const { gallery, voting, ballot } = vi.hoisted(() => ({ gallery: vi.fn(), voting: vi.fn(), ballot: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<typeof import("./api")>()),
  usePublicGallery: () => useQuery({ queryKey: ["gallery"], queryFn: gallery }) }));
vi.mock("../peoplesChoice/PeoplesChoiceVoting", async original => ({ ...(await original<typeof import("../peoplesChoice/PeoplesChoiceVoting")>()),
  usePeoplesChoiceVoting: () => ({ publicQuery: useQuery({ queryKey: ["voting"], queryFn: voting }),
    ballotQuery: useQuery({ queryKey: ["ballot"], queryFn: ballot }), pub: undefined, session: "anonymous", vote: {} }) }));

it.each(["voting", "ballot"])("retries failed %s independently of the successful gallery", async failed => {
  const error = new StructuredApiError(503, { code: "service_unavailable", detail: "Voting unavailable" });
  gallery.mockReset().mockResolvedValue({ count: 0, results: [], next: null, previous: null });
  voting.mockReset().mockResolvedValue({}); ballot.mockReset().mockResolvedValue({});
  const broken = failed === "voting" ? voting : ballot;
  broken.mockRejectedValue(error);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><GalleryPage makerspaceSlug="lab" publicToken="event"
    eventTitle="Projects" onDownload={async () => {}} projectHref={id => "/projects/" + id} renderMemberCard={() => null} />
  </MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText("No projects are public yet.")).toBeVisible();
  fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
  await waitFor(() => expect(broken).toHaveBeenCalledTimes(2));
  expect(gallery).toHaveBeenCalledTimes(1);
  expect(failed === "voting" ? ballot : voting).toHaveBeenCalledTimes(1);
  const actual = client.getQueryState([failed])!.error as StructuredApiError;
  expect({ status: actual.status, code: actual.code }).toEqual({ status: 503, code: "service_unavailable" });
});
