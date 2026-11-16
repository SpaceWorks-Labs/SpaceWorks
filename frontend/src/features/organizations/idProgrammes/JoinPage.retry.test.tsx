import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";

const api = vi.hoisted(() => ({ getAccessToken: vi.fn(), refreshAccessToken: vi.fn(), publicV1Request: vi.fn(), memberRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...await original<typeof import("../../../lib/api")>(), ...api }));
vi.mock("../../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Programme member sign-in panel</p> }));
vi.mock("../../../components/photo-crop/PhotoPicker", () => ({ PhotoPicker: () => null }));
import { JoinPage } from "./JoinPage";

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/o/synthetic/ids/acceptance"]}>
    <Routes><Route path="/o/:organizationSlug/ids/:programmeSlug" element={<JoinPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}
beforeEach(() => { vi.clearAllMocks(); api.getAccessToken.mockReturnValue("token"); });

// Decision 588: Retry only where a retry can succeed (5xx, 429, no response); a refusal gets the Home way out.
it("offers Retry for an outage and reads the programme again when pressed", async () => {
  api.publicV1Request.mockRejectedValue(new StructuredApiError(503, { code: "service_unavailable", detail: "Programmes are down." }));
  show();
  expect(await screen.findByText("Programmes are down.")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(api.publicV1Request).toHaveBeenCalledTimes(2));
});

it("offers Retry after a rate limit", async () => {
  api.publicV1Request.mockRejectedValue(new StructuredApiError(429, { code: "throttled", detail: "Slow down." }));
  show();
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
});

it("explains a 403 refusal with the Home way out and no Retry", async () => {
  api.publicV1Request.mockRejectedValue(new StructuredApiError(403, { code: "permission_denied", detail: "This programme is for staff only." }));
  show();
  expect(await screen.findByText("This programme is for staff only.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
  expect(api.publicV1Request).toHaveBeenCalledTimes(1);
});

it.each(["not_found", "module_disabled"])("keeps a 404 %s as the one enumeration-safe answer, without Retry", async code => {
  api.publicV1Request.mockRejectedValue(new StructuredApiError(404, { code, detail: "Not found." }));
  show();
  expect(await screen.findByText("The link may be wrong, or the programme has closed.")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
  expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/");
});
