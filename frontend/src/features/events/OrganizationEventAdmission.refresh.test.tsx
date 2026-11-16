import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, clearAccessToken, setAccessToken } from "../../lib/api";
import { OrganizationEventAdmission, organizationEligibilityKey } from "./OrganizationEventAdmission";
import type { PublicEventDetail } from "./eventTicketTypes";

vi.mock("../members/MemberAuthPanel", () => ({ MemberAuthPanel: () => <p>Sign in form</p> }));
// useChargesOn (#184 G5, 14992cc1) reads the tenant: a single space whose events/bookings/loans charge.
vi.mock("../../lib/tenant", () => ({ useTenantPath: () => (path: string) => `/m/venue/${path}`,
  useTenant: () => ({ mode: "single", bootstrap: { charges_tracked: { events: true, bookings: true, loans: true } } }) }));

const event: PublicEventDetail = {
  title: "Workshop", description: "Workshop details", location: "Host venue",
  starts_at: "2026-10-20T10:00:00Z", ends_at: "2026-10-20T12:00:00Z",
  capacity: 10, payment_amount: "0.00", currency: "USD",
  effective_registration_cutoff_at: null, image_url: null, status: "published", series: null,
  public_token: "event-one", registration_audience: "participating_organizations",
  registration_open: true, registration_requires_approval: false, availability: "Available",
  custom_form: [{ id: "reason", label: "Why attend?", type: "short_text", required: true, options: [] }],
};
const allowed = { eligible: true, reason: null, host_waiver: null };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { "Content-Type": "application/json" },
});

describe("eligibility session recovery", () => {
  beforeEach(() => {
    setAccessToken("expired-access");
    cacheTenantPublishableKey("venue", "pk-venue");
    cacheTenantPublishableKey("other", "pk-other");
  });
  afterEach(() => { vi.unstubAllGlobals(); clearAccessToken(); });

  it("refreshes consent repair after eligibility succeeds and retries the same tenant and acceptance", async () => {
    let saved = false;
    const waiver = { id: 4, version: "v2", body: "Current host terms" };
    const request = vi.fn(async (url: string, options?: RequestInit): Promise<Response> => {
      if (url.endsWith("/auth/me")) return json({ id: 17 });
      if (url.endsWith("/auth/refresh")) return json({ access: "refreshed-access" });
      if (url.endsWith("/eligibility/")) return json(saved ? allowed : {
        eligible: false, reason: "host_waiver_required", consent_repair_required: true, host_waiver: waiver,
      });
      if (url.endsWith("/register/")) {
        if (new Headers(options?.headers).get("Authorization") !== "Bearer refreshed-access") {
          return json({ detail: "Token expired" }, 401);
        }
        saved = true;
        return json({ registration_id: 7, status: "waitlisted" });
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", request);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}>
      <OrganizationEventAdmission event={event} makerspaceSlug="venue" />
    </QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: /I accept this host waiver/ }));
    fireEvent.click(screen.getByRole("button", { name: "Save consent" }));
    await screen.findByText("Your registration consent has been updated.");
    const posts = request.mock.calls.filter(([url]) => url.endsWith("/register/"));
    expect(posts).toHaveLength(2);
    expect(request.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    for (const [url, options] of posts) {
      expect(url).toMatch(/\/public\/venue\/events\/event-one\/register\/$/);
      expect(options?.method).toBe("POST");
      expect(options?.body).toBe(JSON.stringify({ host_waiver_id: 4,
        host_waiver_version: "v2", host_waiver_accepted: true }));
      expect(new Headers(options?.headers).get("X-Publishable-Key")).toBe("pk-venue");
    }
    expect(new Headers(posts[0][1]?.headers).get("Authorization")).toBe("Bearer expired-access");
    expect(new Headers(posts[1][1]?.headers).get("Authorization")).toBe("Bearer refreshed-access");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    view.unmount(); client.clear();
  });

  it("refreshes an expired access token and preserves answers in the mounted form", async () => {
    let expired = false;
    let finishRefresh: ((response: Response) => void) | undefined;
    const request = vi.fn(async (url: string, options?: RequestInit): Promise<Response> => {
      if (url.endsWith("/auth/me")) return json({ id: 17 });
      if (url.endsWith("/auth/refresh")) return new Promise(resolve => { finishRefresh = resolve; });
      if (url.endsWith("/eligibility/")) {
        const headers = new Headers(options?.headers);
        expect(headers.get("X-Publishable-Key")).toBe("pk-venue");
        return expired && headers.get("Authorization") !== "Bearer refreshed-access"
          ? json({ detail: "Token expired" }, 401) : json(allowed);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", request);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<MemoryRouter><QueryClientProvider client={client}>
      <OrganizationEventAdmission event={event} makerspaceSlug="venue" />
    </QueryClientProvider></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
    fireEvent.click(await screen.findByRole("button", { name: "Register" }));
    const answer = screen.getByRole("textbox", { name: /Why attend/ });
    fireEvent.change(answer, { target: { value: "Build a telescope" } });

    expired = true;
    let refreshed: Promise<void>;
    act(() => { refreshed = client.invalidateQueries({ queryKey: organizationEligibilityKey("venue", "event-one", 17) }); });
    await waitFor(() => expect(finishRefresh).toBeDefined());
    expect(answer).toBeInTheDocument();
    expect(answer).toHaveValue("Build a telescope");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await act(async () => {
      finishRefresh!(json({ access: "refreshed-access" }));
      await refreshed;
    });
    expect(screen.getByRole("textbox", { name: /Why attend/ })).toBe(answer);
    expect(answer).toHaveValue("Build a telescope");
    expect(request.mock.calls.filter(([url]) => url.endsWith("/eligibility/"))).toHaveLength(3);
    expect(request.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    view.unmount(); client.clear();
  });

  it("offers sign-in when eligibility cannot recover an expired refresh session", async () => {
    const request = vi.fn(async (url: string) => {
      if (url.endsWith("/auth/me")) return json({ id: 17 });
      return json({ detail: "Session expired" }, 401);
    });
    vi.stubGlobal("fetch", request);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(<QueryClientProvider client={client}>
      <OrganizationEventAdmission event={event} makerspaceSlug="venue" />
    </QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Check registration eligibility" }));
    await screen.findByText("Sign in form");
    expect(screen.queryByRole("button", { name: "Register" })).not.toBeInTheDocument();
    expect(request.mock.calls.filter(([url]) => url.endsWith("/auth/refresh"))).toHaveLength(1);
    view.unmount(); client.clear();
  });
});
