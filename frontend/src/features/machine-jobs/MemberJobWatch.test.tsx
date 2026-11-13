import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api/errors";
import { MemberJobWatch } from "./MemberJobWatch";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest }));

const wrap = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { mutations: { retry: false } } })}><MemberJobWatch jobId={12} /></QueryClientProvider>);

describe("Watch my job", () => {
  beforeEach(() => { memberRequest.mockReset(); vi.stubGlobal("RTCPeerConnection", undefined); });

  it("opens a watch on the member's own job and shows the five-minute notice", async () => {
    memberRequest.mockImplementation(async (path: string, init?: { method?: string }) => {
      if (path === "/member/adapter-watch/requests/12") return { id: "w9", binding: "b", status: "active", expires_at: new Date(Date.now() + 280_000).toISOString(), created_at: new Date().toISOString(), ended_at: null };
      if (path.includes("/signal")) return { signals: [], ice_servers: [] };
      if (path.includes("/frame")) return { content_type: "image/jpeg", data: "QUJD" };
      return init?.method === "DELETE" ? { id: "w9" } : {};
    });
    wrap();
    expect(screen.getByText(/a watch lasts five minutes/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Watch my job" }));
    expect(await screen.findByRole("img", { name: "Camera view of your machine" })).toBeVisible();
    expect(memberRequest).toHaveBeenCalledWith("/member/adapter-watch/requests/12", { method: "POST", body: undefined });
    fireEvent.click(screen.getByRole("button", { name: "Stop watching" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/adapter-watch/w9", { method: "DELETE" }));
    expect(await screen.findByRole("button", { name: "Watch my job" })).toBeVisible();
  });

  it("says plainly when the machine has no camera to watch", async () => {
    memberRequest.mockRejectedValue(new StructuredApiError(404, {}));
    wrap();
    fireEvent.click(screen.getByRole("button", { name: "Watch my job" }));
    expect(await screen.findByText("No camera to show.")).toBeVisible();
  });
});
