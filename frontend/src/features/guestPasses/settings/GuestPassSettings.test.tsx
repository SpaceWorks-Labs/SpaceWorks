import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { DayPassProductsSettings } from "./DayPassProductsSettings";
import { GuestPassPolicySettings } from "./GuestPassPolicySettings";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const policy = {
  guest_borrowing_mode: "none", guest_machine_mode: "none", sponsored_liability: "guest", walk_in_registration_creates: "guest_pass",
  waiver_required_on_site: true, waiver_gate_without_passes: false, sponsor_min_tenure_days: 0, max_concurrent_guests_per_sponsor: 2, sponsor_must_be_present: false,
  visits_before_join_prompt: 3, hard_visit_cap: null, day_pass_daily_cap: null,
};
const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);

describe("GuestPassPolicySettings", () => {
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "PATCH" ? { ...policy, ...JSON.parse(options.body as string) } : policy);
  });

  it("saves the changed borrowing mode and visit cap", async () => {
    wrap(<GuestPassPolicySettings makerspaceId={3} />);
    const borrowing = await screen.findByRole("combobox", { name: "Guest borrowing" });
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
    fireEvent.change(borrowing, { target: { value: "full_with_deposit" } });
    fireEvent.change(screen.getByLabelText("Visit limit"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-pass-policy", expect.objectContaining({ method: "PATCH" })));
    const body = JSON.parse(vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "PATCH")![1]!.body as string);
    expect(body).toMatchObject({ guest_borrowing_mode: "full_with_deposit", hard_visit_cap: 5, day_pass_daily_cap: null });
  });

  it("leaves the waiver switches to the Visitor waiver section (EV-25)", async () => {
    wrap(<GuestPassPolicySettings makerspaceId={3} />);
    fireEvent.change(await screen.findByRole("combobox", { name: "Guest borrowing" }), { target: { value: "full_with_deposit" } });
    expect(screen.queryByRole("switch", { name: "Require the waiver" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guest-pass-policy", expect.objectContaining({ method: "PATCH" })));
    const body = JSON.parse(vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === "PATCH")![1]!.body as string);
    expect(body).not.toHaveProperty("waiver_required_on_site");
    expect(body).not.toHaveProperty("waiver_gate_without_passes");
  });

  it("shows a load error", async () => {
    vi.mocked(staffRequest).mockRejectedValue(new Error("Policy unavailable"));
    wrap(<GuestPassPolicySettings makerspaceId={3} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Policy unavailable");
  });
});

describe("DayPassProductsSettings", () => {
  const product = { id: 4, name: "Weekend pass", amount: "12.50", currency: "EUR", entitlements: { borrow: "none" }, daily_cap: 10, is_public: true, is_active: true, archived_at: null };
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: RequestInit) => options?.method ? product : path.endsWith("day-pass-products") ? [product] : []);
  });

  it("lists, creates and archives day passes", async () => {
    wrap(<DayPassProductsSettings makerspaceId={3} />);
    expect(await screen.findByText("Weekend pass")).toBeVisible();
    expect(screen.getByText(/10 per day/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Archive" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/day-pass-products/4/archive", { method: "POST", body: "{}" }));
    fireEvent.click(screen.getByRole("button", { name: "Add a day pass" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Name"), { target: { value: "Open day" } });
    fireEvent.change(within(dialog).getByLabelText(/Price/), { target: { value: "0" } });
    fireEvent.change(within(dialog).getByLabelText("Machine use on this pass"), { target: { value: "supervised" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save day pass" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/day-pass-products", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(vi.mocked(staffRequest).mock.calls.find(([path, options]) => String(path).endsWith("day-pass-products") && options?.method === "POST")![1]!.body as string);
    expect(body).toMatchObject({ name: "Open day", amount: "0", currency: "", daily_cap: null, entitlements: { machines: "supervised" } });
  });
});
