import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { expectNoA11yViolations } from "../../test/axe";
import { minutesLabel } from "../machine-service/ServiceRequestEta";
import { MyMachineJobsPage } from "./MyMachineJobsPage";
import { etaWhen, failureText, type MemberJob } from "./types";

const api = vi.hoisted(() => ({ fetchMyJobs: vi.fn() }));
vi.mock("./api", async original => ({ ...(await original<object>()), ...api }));
vi.mock("./MemberJobsShell", () => ({ MemberJobsShell: ({ children }: { children: (context: object) => ReactNode }) => <>{children({
  slug: "lab", makerspaceId: 1, ready: true, bootstrapError: false, path: (part = "") => `/m/lab/${part}` })}</> }));

const base: MemberJob = { id: 1, public_token: "t", makerspace_id: 1, queue_id: 3, can_cancel: false, title: "Old print", status: "collected", label: "collected",
  machine_type_name: "3D printer", machine_name: "", position: null, eta: null, timeline: [], changes_message: "", quote: null,
  quote_expires_at: null, awaiting_payment: false, reason: "", fail_code: "", failure_outcome: "", pickup_code: "", pickup_location: "",
  copies: 1, needed_by: null, created_at: "2026-10-01T09:00:00Z" };

describe("MyMachineJobsPage", () => {
  it("lists the member's jobs, the ones waiting on them first, each linking to its page", async () => {
    api.fetchMyJobs.mockResolvedValue([base, { ...base, id: 2, title: "Sign", label: "quote_sent", status: "quoted", machine_type_name: "Laser cutter" },
      { ...base, id: 3, title: "Bracket", label: "in_queue", status: "accepted", position: 2 }]);
    const { container } = render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><MyMachineJobsPage /></MemoryRouter></QueryClientProvider>);
    const links = await screen.findAllByRole("link", { name: /Sign|Bracket|Old print/ });
    expect(links[0]).toHaveAttribute("href", "/m/lab/member/machine-jobs/2");
    expect(screen.getByText("Laser cutter · Quote waiting for your answer")).toBeInTheDocument();
    expect(screen.getByText("3D printer · #2 in queue")).toBeInTheDocument();
    expect(within(container).getAllByText("Collected").length).toBeGreaterThan(0);
    expect(api.fetchMyJobs).toHaveBeenCalledWith(1);
    await expectNoA11yViolations(container);
  });
});

describe("job copy helpers", () => {
  const now = new Date(2026, 10, 2, 9, 0);
  it("keeps minutes within a day and switches to a day and a time beyond it", () => {
    expect(etaWhen(new Date(2026, 10, 2, 11, 30).toISOString(), now, minutesLabel)).toBe("in about 2 h 30 min");
    expect(etaWhen(new Date(2026, 10, 5, 14, 0).toISOString(), now, minutesLabel)).toBe("Thu, about 14:00");
    expect(etaWhen(new Date(2026, 10, 1).toISOString(), now, minutesLabel)).toBe("now");
  });
  it("words each failure outcome", () => {
    expect(failureText({ fail_code: "power_cut", failure_outcome: "free", reason: "" })).toBe("Failed: power cut — no charge");
    expect(failureText({ fail_code: "", failure_outcome: "staff_decide", reason: "" })).toBe("Failed — staff will tell you what happens next");
  });
});
