import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { Choices } from "./Choices";

const mocks = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: mocks.request }));

it("loads an authorized space before selecting an exact booking", async () => {
  mocks.request.mockReset();
  mocks.request.mockImplementation((path: string) => {
    if (path === "/admin/makerspaces/4/spaces/?page=1") return Promise.resolve({ results: [{ id: 8, name: "Workshop" }], next: null, previous: null });
    if (path === "/admin/spaces/8/bookings/?page=1&ordering=starts_at") return Promise.resolve({ results: [{ id: 23, name: "Private borrower", starts_at: "2030-01-01T10:00:00Z" }], next: null, previous: null });
    throw new Error(`Unexpected route ${path}`);
  });
  const select = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Choices tenant={4} domain="booking" scope="actor:1:tenant:4" onSelect={select} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Workshop" }));
  const booking = await screen.findByRole("button", { name: /^Booking #23/ });
  expect(screen.queryByText("Private borrower")).toBeNull();
  fireEvent.click(booking);
  expect(select).toHaveBeenCalledTimes(1);
  expect(select).toHaveBeenCalledWith(23);
  await waitFor(() => expect(mocks.request.mock.calls.map(call => call[0])).toEqual([
    "/admin/makerspaces/4/spaces/?page=1", "/admin/spaces/8/bookings/?page=1&ordering=starts_at",
  ]));
});


it("discovers only the actor's accessible events for this tenant", async () => {
  mocks.request.mockReset();
  mocks.request.mockImplementation((path: string) => {
    if (path === "/admin/accessible-events/?page=1&makerspace_id=4") return Promise.resolve({ results: [{ id: 19, title: "Granted event" }], next: null, previous: null });
    throw new Error(`Unexpected route ${path}`);
  });
  const select = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Choices tenant={4} domain="event" scope="delegate:tenant:4" onSelect={select} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "Granted event" }));
  expect(select).toHaveBeenCalledTimes(1);
  expect(select).toHaveBeenCalledWith(19);
  expect(mocks.request).toHaveBeenCalledWith("/admin/accessible-events/?page=1&makerspace_id=4");
});
