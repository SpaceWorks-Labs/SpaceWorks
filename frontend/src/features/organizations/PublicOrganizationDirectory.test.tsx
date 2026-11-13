import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../lib/api/errors";
import { PublicOrganizationDirectory } from "./PublicOrganizationDirectory";
import type { DirectoryOrganization } from "./publicDirectoryApi";

const { publicV1Request } = vi.hoisted(() => ({ publicV1Request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), publicV1Request }));
vi.mock("../NotFoundPage", () => ({ NotFoundPage: () => <p>Page not found</p> }));

const org = (name: string, slug: string, extra: Partial<DirectoryOrganization> = {}): DirectoryOrganization => ({
  name, slug, description: `${name} runs workshops.`, logo_url: null, canonical_url: `${window.location.origin}/o/${slug}`, ...extra,
});
const page = (results: DirectoryOrganization[], count = results.length) => ({ count, next: null, previous: null, results });

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={["/organizations"]}><Routes><Route path="/organizations" element={<PublicOrganizationDirectory />} /></Routes></MemoryRouter>
  </QueryClientProvider>);
}

beforeEach(() => { publicV1Request.mockReset(); });

describe("PublicOrganizationDirectory", () => {
  it("is a not-found page while the directory switch is off (the server answers 404)", async () => {
    publicV1Request.mockRejectedValue(new StructuredApiError(404, { detail: "Not found." }));
    show();
    expect(await screen.findByText("Page not found")).toBeInTheDocument();
  });

  it("lists organizations as cards that link to their public pages", async () => {
    publicV1Request.mockResolvedValue(page([org("Harbour Makers", "harbour-makers"), org("North Guild", "north-guild"), org("Quay Club", "quay-club")]));
    show();
    expect(screen.getByRole("heading", { level: 1, name: "Organizations on Space Works" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Harbour Makers" })).toHaveAttribute("href", "/o/harbour-makers");
    expect(screen.getByText("3 organizations")).toBeInTheDocument();
    expect(publicV1Request).toHaveBeenCalledWith("/public/organizations/?page=1", { cache: "no-store" });
  });

  it("searches by name on the server and offers a way back when nothing matches", async () => {
    publicV1Request.mockImplementation(async (path: string) => path.includes("search=") ? page([]) : page([org("Harbour Makers", "harbour-makers")]));
    show();
    await screen.findByRole("link", { name: "Harbour Makers" });
    fireEvent.change(screen.getByRole("searchbox", { name: "Search organizations" }), { target: { value: "zebra" } });
    expect(await screen.findByText("No organizations match “zebra”")).toBeInTheDocument();
    expect(publicV1Request).toHaveBeenCalledWith("/public/organizations/?page=1&search=zebra", { cache: "no-store" });
    fireEvent.click(screen.getByRole("button", { name: "Clear search" }));
    expect(await screen.findByRole("link", { name: "Harbour Makers" })).toBeInTheDocument();
  });

  it("says when nothing is listed yet", async () => {
    publicV1Request.mockResolvedValue(page([]));
    show();
    expect(await screen.findByText("No organizations listed yet")).toBeInTheDocument();
  });

  it("offers a retry when the list fails", async () => {
    publicV1Request.mockRejectedValue(new StructuredApiError(503, { detail: "Unavailable" }));
    show();
    // A 5xx is retried once automatically before the error state shows.
    const retry = await screen.findByRole("button", { name: "Retry" }, { timeout: 5000 });
    expect(screen.getByText("Couldn't load organizations")).toBeInTheDocument();
    publicV1Request.mockResolvedValue(page([org("Harbour Makers", "harbour-makers")]));
    fireEvent.click(retry);
    await waitFor(() => expect(screen.getByRole("link", { name: "Harbour Makers" })).toBeInTheDocument());
  });

  it("pages 24 at a time", async () => {
    publicV1Request.mockResolvedValue(page(Array.from({ length: 24 }, (_, i) => org(`Org ${i + 1}`, `org-${i + 1}`)), 30));
    show();
    await screen.findByRole("link", { name: "Org 1" });
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    await waitFor(() => expect(publicV1Request).toHaveBeenCalledWith("/public/organizations/?page=2", { cache: "no-store" }));
  });
});
