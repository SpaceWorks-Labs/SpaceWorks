import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MemberSession } from "./api";
import { MySessionsPage } from "./MySessionsPage";

const api = vi.hoisted(() => ({ fetchMySessions: vi.fn() }));
const { memberRequest } = vi.hoisted(() => ({ memberRequest: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
vi.mock("../../lib/api", async original => ({ ...(await original<object>()), memberRequest }));
const features = vi.hoisted(() => ({ list: [] as string[] }));
vi.mock("../machine-jobs/MemberJobsShell", () => ({ MemberJobsShell: ({ children }: { children: (context: object) => ReactNode }) => <>{children({
  slug: "lab", makerspaceId: 1, ready: true, bootstrapError: false, path: (part = "") => `/m/lab/${part}`, features: features.list })}</> }));

const session: MemberSession = { id: 5, makerspace_id: 1, machine_id: 3, machine_name: "Laser A", machine_type_name: "Laser cutter",
  source: "member_qr", status: "closed", started_at: "2026-11-02T09:00:00Z", ended_at: "2026-11-02T10:00:00Z", minutes: 60,
  stop_reason: "member", flagged: false, charge_state: "none", rate: null, amount: null, payment: null };

const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <MemoryRouter><MySessionsPage /></MemoryRouter></QueryClientProvider>);

beforeEach(() => { api.fetchMySessions.mockReset().mockResolvedValue([session]); memberRequest.mockReset(); });

describe("report a problem from a machine session (decision 220(d)2)", () => {
  it("files the report against the member's own session while machine reporting is on", async () => {
    features.list = ["machines.issue_reporting"];
    memberRequest.mockResolvedValue({ id: 1, state: "reported" });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Report a problem with the machine" }));
    fireEvent.change(screen.getByLabelText("What's wrong"), { target: { value: "Bed not level" } });
    fireEvent.change(screen.getByLabelText("Details"), { target: { value: "It drifted." } });
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith("/member/issues", { method: "POST", body: JSON.stringify({
      makerspace_id: 1, machine_session_id: 5, title: "Bed not level", description: "It drifted.", photos: [] }) }));
  });

  it("offers no button while machine reporting is off", async () => {
    features.list = [];
    show();
    expect(await screen.findByText("Laser A")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Report a problem with the machine" })).toBeNull();
  });
});
