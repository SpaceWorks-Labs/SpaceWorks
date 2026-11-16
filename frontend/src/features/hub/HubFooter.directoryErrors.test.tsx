import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { publicV1Request, StructuredApiError } from "../../lib/api";
import { directoryKey } from "../organizations/publicDirectoryApi";
import { DocsPage } from "../docs/DocsPage";
import { FeaturesPage } from "./FeaturesPage";
import { HubLandingPage } from "./HubLandingPage";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), publicV1Request: vi.fn() }));
vi.mock("../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false, isPending: false }) }));
vi.mock("./useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: true }) }));
vi.mock("../inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => ({ data: [], isLoading: false }) }));

const pages = [
  ["/", "Run the space, not spreadsheets.", HubLandingPage],
  ["/features", "Everything Space Works does, module by module.", FeaturesPage],
  ["/docs/*", "Space Works documentation", DocsPage],
] as const;

it.each(pages)("keeps %s healthy when the directory answers 404 not_found", async (path, heading, Page) => {
  vi.mocked(publicV1Request).mockReset().mockRejectedValue(new StructuredApiError(404, { code: "not_found", detail: "Directory disabled" }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path.replace("/*", "")]}><Routes>
    <Route path={path} element={<Page />} />
  </Routes></MemoryRouter></QueryClientProvider>);
  await waitFor(() => expect(client.getQueryState(directoryKey(1, ""))?.status).toBe("error"));
  const error = client.getQueryState(directoryKey(1, ""))?.error as StructuredApiError;
  expect([error.status, error.code]).toEqual([404, "not_found"]);
  expect(screen.getByRole("heading", { level: 1, name: heading })).toBeVisible();
  expect(screen.queryByRole("link", { name: "Organizations" })).toBeNull();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  expect(publicV1Request).toHaveBeenCalledTimes(1);
});

it("retries a genuine 503 service_unavailable directory outage and restores its link", async () => {
  vi.mocked(publicV1Request).mockReset().mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "Directory unavailable" }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
  render(<QueryClientProvider client={client}><MemoryRouter><FeaturesPage /></MemoryRouter></QueryClientProvider>);
  await screen.findByRole("alert");
  const error = client.getQueryState(directoryKey(1, ""))?.error as StructuredApiError;
  expect([error.status, error.code]).toEqual([503, "service_unavailable"]);
  expect(screen.queryByRole("link", { name: "Organizations" })).toBeNull();
  expect(publicV1Request).toHaveBeenCalledTimes(2);
  vi.mocked(publicV1Request).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await screen.findByRole("link", { name: "Organizations" });
  expect(publicV1Request).toHaveBeenCalledTimes(3);
  expect(screen.queryByRole("alert")).toBeNull();
});
