import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SupervisedSessionsPage } from "./SupervisedSessionsPage";

const api = vi.hoisted(() => ({ memberRequest: vi.fn(), features: [] as string[] }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest: api.memberRequest }));
vi.mock("../machine-jobs/MemberJobsShell", () => ({ MemberJobsShell: ({ children }: { children: (context: object) => ReactNode }) => <>{children({
  slug: "lab", makerspaceId: 1, ready: true, bootstrapError: false, features: api.features, path: (part = "") => `/m/lab/${part}` })}</> }));

function show(path: string) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/m/:slug/machines/:machineId/supervise" element={<SupervisedSessionsPage />} />
      <Route path="/m/:slug/member/supervised-sessions" element={<SupervisedSessionsPage />} />
    </Routes></MemoryRouter></QueryClientProvider>);
}

describe("SupervisedSessionsPage", () => {
  beforeEach(() => { api.memberRequest.mockReset(); api.memberRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] }); });

  it("says the feature is not offered while machines.supervised_sessions is off, without calling the API", async () => {
    api.features = [];
    show("/m/lab/member/supervised-sessions");
    expect(await screen.findByText(/Supervised sessions aren't offered here/)).toBeInTheDocument();
    expect(api.memberRequest).not.toHaveBeenCalled();
  });

  it("starts on the machine from its supervise link without asking for a machine number", async () => {
    api.features = ["machines.supervised_sessions"];
    show("/m/lab/machines/3/supervise");
    expect(await screen.findByRole("heading", { name: "Start a supervised session" })).toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Machine number" })).toBeNull();
    expect(api.memberRequest).toHaveBeenCalledWith("/member/makerspaces/1/supervised-sessions?status=open&page=1&machine=3");
  });
});
