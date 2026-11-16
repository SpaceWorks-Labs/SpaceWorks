import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HostingSwitchSection } from "./HostingSwitchSection";
import { RequestRatesSection } from "./RequestRatesSection";
import { SpaceLimitsSection } from "./SpaceLimitsSection";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

const mount = (ui: React.ReactElement) => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>{ui}</QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

describe("hosting switch, limits and request rates (decision 234)", () => {
  it("turns hosting on and audits through the PUT", async () => {
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) =>
      init?.method === "PUT" ? { enabled: true, forced_by_environment: false } : { enabled: false, forced_by_environment: false });
    mount(<HostingSwitchSection />);
    fireEvent.click(await screen.findByRole("checkbox"));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/hosting-switch",
      { method: "PUT", body: JSON.stringify({ enabled: true }) }, "platform"));
  });

  it("locks the switch when the environment forces it", async () => {
    staffRequest.mockResolvedValue({ enabled: true, forced_by_environment: true });
    mount(<HostingSwitchSection />);
    expect(await screen.findByRole("checkbox")).toBeDisabled();
    expect(screen.getByText("Set by the server (MANAGED_PLANS_ENABLED). Remove that setting to control it here.")).toBeVisible();
  });

  it("explains the switch in plain words and links its guide", async () => {
    staffRequest.mockResolvedValue({ enabled: false, forced_by_environment: false });
    mount(<HostingSwitchSection />);
    expect(await screen.findByText(/Lets this install host other makerspaces/)).toBeVisible();
    expect(screen.queryByText(/MANAGED_PLANS_ENABLED/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /How hosting other makerspaces works/ }))
      .toHaveAttribute("href", expect.stringContaining("docs/self-hosting.md#plans-and-hosting-other-makerspaces-optional"));
  });

  it("shows usage next to a limit and saves an override", async () => {
    const data = { custom_domain: false, hosted: true, rows: [{ key: "members", label: "members", unit: "count", effective: 25, source: "plan",
      override: null, has_override: false, used: 3, suggested: 25 }] };
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method === "PUT" ? data : data);
    mount(<SpaceLimitsSection makerspaceId={7} />);
    expect(await screen.findByText(/Using 3 of 25/)).toBeInTheDocument();
    expect(screen.getByText("Members")).toBeVisible();
    expect(screen.getByText(/At the limit, new joins wait/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Limit for this space: Members"), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Save limits" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/spaces/7/limits",
      { method: "PUT", body: JSON.stringify({ overrides: { members: 50 } }) }, "platform"));
  });

  it("says when the limits could not load and retries them (LM-4)", async () => {
    const data = { custom_domain: false, hosted: true, rows: [{ key: "members", label: "members", unit: "count", effective: 25, source: "plan",
      override: null, has_override: false, used: 3, suggested: 25 }] };
    staffRequest.mockRejectedValueOnce(new Error("offline")).mockResolvedValue(data);
    mount(<SpaceLimitsSection makerspaceId={7} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load limits. Try again.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText(/Using 3 of 25/)).toBeInTheDocument();
  });

  it("edits a request rate with its env key shown", async () => {
    const row = { scope: "login", default: "10/min", rate: "10/min", overridden: false, min_rate: "60/hour", max_rate: "6000/hour", env_key: "THROTTLE_LOGIN" };
    staffRequest.mockImplementation(async (_path: string, init?: RequestInit) => init?.method ? row : [row]);
    mount(<RequestRatesSection />);
    expect(await screen.findByText(/THROTTLE_LOGIN/)).toBeInTheDocument();
    expect(screen.getByText("Sign-in attempts")).toBeVisible();
    expect(screen.getByText(/Too many requests/)).toBeVisible();
    fireEvent.change(screen.getByLabelText("Rate for Sign-in attempts"), { target: { value: "20/min" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/platform/request-limits/login",
      { method: "PUT", body: JSON.stringify({ rate: "20/min" }) }, "platform"));
  });
});
