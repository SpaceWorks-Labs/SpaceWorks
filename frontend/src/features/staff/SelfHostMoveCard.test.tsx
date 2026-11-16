import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SelfHostMoveCard } from "./SelfHostMoveCard";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));

const PATH = "/admin/makerspace/7/selfhost-move-request";
const REQUEST = {
  id: "move-1", status: "requested", status_label: "Requested", note: "Soon", requested_at: new Date().toISOString(),
  decided_at: null, decision_note: "", exported_at: null,
};

function renderCard() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SelfHostMoveCard makerspaceId={7} />
  </QueryClientProvider>);
}

beforeEach(() => { staffRequest.mockReset(); });

describe("SelfHostMoveCard", () => {
  it("sends a request with the note and then shows its status instead of the form", async () => {
    staffRequest.mockImplementation((_path: string, options?: RequestInit) =>
      Promise.resolve(options?.method === "POST" ? { request: REQUEST } : { request: null }));
    renderCard();
    fireEvent.change(await screen.findByRole("textbox", { name: /note for the platform operator/i }),
      { target: { value: "Soon" } });
    fireEvent.click(screen.getByRole("button", { name: "Request a move to self-host" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(PATH, { method: "POST", body: JSON.stringify({ note: "Soon" }) }));
    expect(await screen.findByText("Your move request")).toBeVisible();
    expect(staffRequest).toHaveBeenCalledWith(PATH);
    expect(screen.queryByRole("button", { name: "Request a move to self-host" })).toBeNull();
    expect(screen.getByText(/you do not download anything here/i)).toBeVisible();
  });

  it("lets a declined space ask again and shows the operator's note", async () => {
    staffRequest.mockResolvedValue({ request: { ...REQUEST, status: "rejected", status_label: "Rejected", decision_note: "Not yet" } });
    renderCard();
    expect(await screen.findByText("Not yet")).toBeVisible();
    expect(screen.getByRole("button", { name: "Request a move to self-host" })).toBeEnabled();
  });
});
