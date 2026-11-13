import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MemberJobMedia } from "./MemberJobMedia";

const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest }));

const now = new Date().toISOString();
const wrap = (props: { artifacts: boolean; detections: boolean }) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemberJobMedia jobId={12} {...props} /></QueryClientProvider>);

describe("From your machine", () => {
  beforeEach(() => { memberRequest.mockReset(); });

  it("shows the owner their own job's pictures and alerts, without staff notes", async () => {
    memberRequest.mockImplementation(async (path: string) => {
      if (path === "/member/adapter-artifacts/requests/12") return { count: 1, next: null, previous: null, results: [{ id: "x1", binding: "b", kind: "thumbnail", content_type: "image/jpeg", size_bytes: 2048, status: "ready", service_request_id: 12, session_id: null, captured_at: now, created_at: now, expires_at: now }] };
      if (path === "/member/adapter-detections/requests/12") return { count: 1, next: null, previous: null, results: [{ id: "d1", kind: "failure", confidence: 0.8, artifact_id: null, observed_at: now }] };
      if (path === "/member/adapter-artifacts/x1/url") return { url: "https://s.test/t.jpg", content_type: "image/jpeg", kind: "thumbnail" };
      return {};
    });
    wrap({ artifacts: true, detections: true });
    expect(await screen.findByRole("heading", { name: "From your machine" })).toBeVisible();
    expect(await screen.findByText("Print failure")).toBeVisible();
    expect(await screen.findByRole("img", { name: "Thumbnail" })).toHaveAttribute("src", "https://s.test/t.jpg");
    expect(screen.queryByText(/staff only/)).toBeNull();
  });

  it("renders nothing while there is nothing to show, and does not ask for what its switch hides", async () => {
    memberRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    const { container } = wrap({ artifacts: true, detections: false });
    await vi.waitFor(() => expect(memberRequest).toHaveBeenCalledTimes(1));
    expect(memberRequest).toHaveBeenCalledWith("/member/adapter-artifacts/requests/12");
    expect(container.querySelector("section")).toBeNull();
  });

  it("says so when the server refuses", async () => {
    memberRequest.mockRejectedValue(new Error("boom"));
    wrap({ artifacts: true, detections: false });
    expect(await screen.findByRole("alert")).toBeVisible();
  });
});
