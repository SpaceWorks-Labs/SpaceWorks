import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { staffRequest } from "../../lib/api";
import { StructuredApiError } from "../../lib/api/errors";
import { OrganizationSelfCreation, useOrganizationSelfCreationVisible } from "./OrganizationSelfCreation";

vi.mock("../../lib/api", async original => ({ ...(await original<typeof import("../../lib/api")>()), staffRequest: vi.fn(), getAccessToken: () => null }));
vi.mock("../../lib/tenant", () => ({ useTenant: () => ({ mode: "central" }) }));
function Parent() {
  return <main>{useOrganizationSelfCreationVisible() ? <OrganizationSelfCreation /> : null}</main>;
}
it("keeps a failed shared policy stable when the error reveals its editor, then retries exactly once", async () => {
  const error = new StructuredApiError(503, { code: "service_unavailable", detail: "Policy unavailable" });
  vi.mocked(staffRequest).mockReset().mockRejectedValue(error);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><Parent /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  expect(staffRequest).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  expect(await screen.findByRole("button", { name: "Retry" })).toBeVisible();
  await act(async () => { await new Promise(resolve => setTimeout(resolve, 0)); });
  expect(staffRequest).toHaveBeenCalledTimes(2);
  expect(client.getQueryCache().getAll()[0].state.error).toBe(error);
  expect({ status: error.status, code: error.code }).toEqual({ status: 503, code: "service_unavailable" });
});
