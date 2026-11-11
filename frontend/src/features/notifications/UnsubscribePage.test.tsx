import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), publicV1Request: request }));

import { UnsubscribePage } from "./UnsubscribePage";

const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}>
  <MemoryRouter initialEntries={["/unsubscribe/abc:def"]}><Routes><Route path="/unsubscribe/:token" element={<UnsubscribePage />} /></Routes></MemoryRouter>
</QueryClientProvider>);

beforeEach(() => { request.mockReset(); });

it("changes nothing on open and sends the one-click body only on confirmation", async () => {
  request.mockResolvedValue({ detail: "Optional emails for this family are disabled. Safety emails remain enabled." });
  mount();
  expect(screen.getByRole("heading", { name: "Stop these emails?" })).toBeInTheDocument();
  expect(request).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));
  expect(await screen.findByRole("heading", { name: "You're unsubscribed" })).toBeInTheDocument();
  expect(request).toHaveBeenCalledWith("/notifications/unsubscribe/abc%3Adef",
    { method: "POST", body: JSON.stringify({ "List-Unsubscribe": "One-Click" }) });
  expect(screen.getByText("Optional emails for this family are disabled. Safety emails remain enabled.")).toBeInTheDocument();
});

it("explains an expired or invalid link", async () => {
  request.mockRejectedValue(new Error("Invalid or expired unsubscribe token."));
  mount();
  fireEvent.click(screen.getByRole("button", { name: "Unsubscribe" }));
  expect(await screen.findByRole("heading", { name: "This link didn't work" })).toBeInTheDocument();
});
