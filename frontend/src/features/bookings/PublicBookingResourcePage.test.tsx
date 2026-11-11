import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cacheTenantPublishableKey, clearAccessToken, getAccessToken, setAccessToken } from "../../lib/api";
import { TenantProvider } from "../../lib/tenant";
import { PublicBookingResourcePage } from "./PublicBookingResourcePage";

vi.mock("../members/MemberAuthPanel", () => ({
  MemberAuthPanel: ({ makerspaceSlug, onAuthenticated }: { makerspaceSlug: string; onAuthenticated: () => void }) =>
    <button onClick={() => { setAccessToken("signed-in-member"); onAuthenticated(); }}>Sign in to {makerspaceSlug}</button>,
}));

const resource = {
  public_token: "room-token", name: "Workshop", kind: "bench", description: "Public resource details",
  location: "Upstairs", capacity: 3, image_url: "", approval_mode: "instant", custom_form: null,
  payment_amount: "0.00", currency: "inr", website: null,
  rules: { minimum_minutes: 30, maximum_minutes: 120, lead_minutes: 0, advance_days: 30, cancellation_cutoff_hours: 24 },
};
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
let refresh: () => Promise<Response>;
let bookingHeaders: Headers | undefined;
let bookingResponse: () => Response;

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/m/lab/bookings/room-token"]}>
    <TenantProvider><Routes><Route path="/m/:slug/bookings/:resourceToken" element={<PublicBookingResourcePage />} /></Routes></TenantProvider>
  </MemoryRouter></QueryClientProvider>);
}

async function submit() {
  fireEvent.change(await screen.findByLabelText("Starts"), { target: { value: "2099-01-01T10:00" } });
  fireEvent.change(screen.getByLabelText("Ends"), { target: { value: "2099-01-01T11:00" } });
  fireEvent.click(screen.getByRole("button", { name: "Book this slot" }));
  await screen.findByText("Space booked");
}

beforeEach(() => {
  clearAccessToken();
  cacheTenantPublishableKey("lab", "public-lab-key");
  bookingHeaders = undefined;
  bookingResponse = () => json({ status: "confirmed" });
  // Tablet/desktop width: the booking form renders inline in the action card rather than behind the phone sheet.
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: true, media: query, addEventListener: () => {}, removeEventListener: () => {} }));
  refresh = async () => json({ access: "restored-member" });
  vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/auth/refresh")) {
      expect(init).toMatchObject({ method: "POST", credentials: "include" });
      return refresh();
    }
    if (url.includes("/availability/")) return json({ availability: [], opening_intervals: [], timezone: "UTC" });
    if (url.endsWith("/book/")) {
      bookingHeaders = new Headers(init?.headers);
      return bookingResponse();
    }
    if (url.endsWith("/spaces/room-token/")) return json(resource);
    // The public chrome loads the tenant bootstrap for its header; this suite does not need one.
    if (url.includes("/bootstrap?")) return json({ detail: "Not found." }, 404);
    throw new Error(`Unexpected request: ${url}`);
  }));
});
afterEach(() => { clearAccessToken(); vi.unstubAllGlobals(); });

describe("direct public resource bookings", () => {
  it("explains a machine certification refusal without claiming the booking succeeded", async () => {
    bookingResponse = () => json({ code: "certification_required", certifications: ["Machine induction"] }, 403);
    setAccessToken("existing-member");
    show();
    fireEvent.change(await screen.findByLabelText("Starts"), { target: { value: "2099-01-01T10:00" } });
    fireEvent.change(screen.getByLabelText("Ends"), { target: { value: "2099-01-01T11:00" } });
    fireEvent.click(screen.getByRole("button", { name: "Book this slot" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You need machine training or certification first (Machine induction). Ask space staff how to qualify, then try again.");
    expect(screen.queryByText("Space booked")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Starts")).toHaveValue("2099-01-01T10:00");
  });

  it("waits for the refresh cookie session and submits with the restored access token", async () => {
    let resolve!: (value: Response) => void;
    refresh = () => new Promise((done) => { resolve = done; });
    expect(getAccessToken()).toBe("");
    show();
    await screen.findByText("Public resource details");
    expect(screen.getByText("Restoring your session...")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Book this slot" })).not.toBeInTheDocument();
    await act(async () => resolve(json({ access: "restored-member" })));
    await submit();
    expect(bookingHeaders?.get("Authorization")).toBe("Bearer restored-member");
  });

  it("offers sign-in on the resource page when no refresh session exists", async () => {
    refresh = async () => json({}, 401);
    show();
    const signIn = await screen.findByRole("button", { name: "Sign in to lab" });
    expect(screen.queryByRole("button", { name: "Book this slot" })).not.toBeInTheDocument();
    fireEvent.click(signIn);
    await submit();
    expect(bookingHeaders?.get("Authorization")).toBe("Bearer signed-in-member");
    expect(screen.getByRole("heading", { name: "Workshop" })).toBeVisible();
  });

  it("offers sign-in after a refresh network failure", async () => {
    refresh = async () => { throw new Error("Offline"); };
    show();
    expect(await screen.findByRole("button", { name: "Sign in to lab" })).toBeVisible();
    expect(screen.queryByLabelText("Starts")).not.toBeInTheDocument();
  });

  it("keeps an existing access session without attempting a refresh", async () => {
    setAccessToken("existing-member");
    show();
    await waitFor(() => expect(screen.getByLabelText("Starts")).toBeVisible());
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).endsWith("/auth/refresh"))).toBe(false);
    await submit();
    expect(bookingHeaders?.get("Authorization")).toBe("Bearer existing-member");
  });
});
