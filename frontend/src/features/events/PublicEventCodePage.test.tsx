import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { publicV1Request } from "../../lib/api";
import { PublicEventCodePage } from "./PublicEventCodePage";

vi.mock("../../lib/api", async (original) => ({ ...(await original<typeof import("../../lib/api")>()), publicV1Request: vi.fn() }));
vi.mock("../inventory/PublicEventDetailPage", () => ({
  PublicEventDetailPage: ({ resolvedSlug, resolvedToken }: { resolvedSlug: string; resolvedToken: string }) =>
    <p>event {resolvedSlug} {resolvedToken}</p>,
}));
vi.mock("../NotFoundPage", () => ({ NotFoundPage: () => <p>not found</p> }));

const TOKEN = "5f0c3a52-8a1e-4d2b-9a77-0f3c1e2d4b6a";
const resolved = { canonical_url: "https://space.example/e/AbC1234", content_url: `/api/v1/public/tinkerspace/events/${TOKEN}/` };

beforeEach(() => { vi.mocked(publicV1Request).mockReset(); vi.mocked(publicV1Request).mockResolvedValue(resolved as never); });

function open(code: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/e/${code}`]}>
    <Routes><Route path="/e/:publicToken" element={<PublicEventCodePage />} /></Routes></MemoryRouter></QueryClientProvider>);
  return client;
}

it("resolves a 7-character short code and marks only the first load as a visit", async () => {
  const client = open("AbC1234");
  expect(await screen.findByText(`event tinkerspace ${TOKEN}`)).toBeInTheDocument();
  expect(vi.mocked(publicV1Request).mock.calls[0]).toEqual(["/public/event-codes/AbC1234/",
    { cache: "no-store", headers: { "X-SW-Visit": "1" } }]);
  await client.refetchQueries();
  await waitFor(() => expect(vi.mocked(publicV1Request)).toHaveBeenCalledTimes(2));
  expect(vi.mocked(publicV1Request).mock.calls[1][1]).toEqual({ cache: "no-store", headers: {} });
});

it("still resolves the long UUID address without counting a visit", async () => {
  open(TOKEN);
  expect(await screen.findByText(`event tinkerspace ${TOKEN}`)).toBeInTheDocument();
  expect(vi.mocked(publicV1Request).mock.calls[0][1]).toEqual({ cache: "no-store", headers: {} });
});

it("shows not found for any other shape without calling the API", async () => {
  open("too-short");
  expect(await screen.findByText("not found")).toBeInTheDocument();
  expect(vi.mocked(publicV1Request)).not.toHaveBeenCalled();
});
