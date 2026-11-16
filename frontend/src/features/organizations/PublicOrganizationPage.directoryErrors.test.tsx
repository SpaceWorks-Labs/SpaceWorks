import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { publicV1Request, StructuredApiError } from "../../lib/api";
import legacy from "../publicPages/fixtures/review-r2.json";
import { directoryKey } from "./publicDirectoryApi";
import { PublicOrganizationPage } from "./PublicOrganizationPage";

vi.mock("../../lib/api", async original => ({ ...await original<typeof import("../../lib/api")>(), publicV1Request: vi.fn() }));
vi.mock("../publicPages/pageApi", async original => ({ ...await original<typeof import("../publicPages/pageApi")>(),
  usePublicPage: () => ({ data: null }),
}));
vi.mock("./publicOrganizationsApi", () => ({
  usePublicOrganization: () => ({ data: legacy.legacy_organization }),
  usePublicOrganizationSpaces: () => ({ data: { count: 0, results: [] } }),
  usePublicOrganizationEvents: () => ({ data: { count: 0, results: [] } }),
}));

it.each([[404, "not_found"], [404, "module_disabled"], [404, "feature_disabled"], [503, "service_unavailable"]] as const)(
  "keeps an organization profile healthy on directory %s %s", async (status, code) => {
    vi.mocked(publicV1Request).mockReset().mockRejectedValue(new StructuredApiError(status, { code, detail: "Directory unavailable" }));
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
    render(<QueryClientProvider client={client}><MemoryRouter><PublicOrganizationPage profileSlug="builders" /></MemoryRouter></QueryClientProvider>);
    await waitFor(() => expect(client.getQueryState(directoryKey(1, ""))?.status).toBe("error"));
    const error = client.getQueryState(directoryKey(1, ""))?.error as StructuredApiError;
    expect([error.status, error.code]).toEqual([status, code]);
    expect(screen.getByRole("heading", { level: 1, name: legacy.legacy_organization.name })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Organizations" })).toBeNull();
    if (status === 404) {
      expect(screen.queryByRole("alert")).toBeNull();
      expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
      expect(publicV1Request).toHaveBeenCalledTimes(1);
    } else {
      expect(await screen.findByRole("alert")).toHaveTextContent("Directory unavailable");
      expect(publicV1Request).toHaveBeenCalledTimes(2);
      vi.mocked(publicV1Request).mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
      await screen.findByRole("link", { name: "Organizations" });
      expect(publicV1Request).toHaveBeenCalledTimes(3);
      expect(screen.queryByRole("alert")).toBeNull();
    }
  },
);
