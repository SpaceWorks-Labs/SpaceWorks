import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LinkedSignInList } from "./LinkedSignInList";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...(await vi.importActual<object>("../../lib/api")), staffRequest }));

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
  <LinkedSignInList /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("LinkedSignInList", () => {
  it("lists linked providers and unlinks one after confirmation", async () => {
    staffRequest.mockImplementation((_path: string, init?: RequestInit) => Promise.resolve(init?.method === "DELETE" ? undefined
      : [{ provider: "google", created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z" }]));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Unlink Google" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Unlink" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/auth/social/providers/google", { method: "DELETE" }));
    expect(await screen.findByText("Google is no longer linked.")).toBeInTheDocument();
  });

  it("shows an empty state with nothing linked", async () => {
    staffRequest.mockResolvedValue([]);
    show();
    expect(await screen.findByText("No sign-in accounts are linked.")).toBeInTheDocument();
  });
});
