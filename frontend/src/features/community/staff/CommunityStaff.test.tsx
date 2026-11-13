import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { staffRequest } from "../../../lib/api";
import { communityMemberTabs } from "./CommunityMemberTabs";
import { MinorsDesk } from "./MinorsDesk";
import { VolunteerQueue } from "./VolunteerQueue";

vi.mock("../../../lib/api", async (original) => ({ ...(await original<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));

const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>);
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });

describe("communityMemberTabs", () => {
  it("shows each Members section only while its capability and the module are on", () => {
    expect(communityMemberTabs(["membership.guest_passes", "membership.minors"], true).map((tab) => tab.key)).toEqual(["guests", "minors"]);
    expect(communityMemberTabs(["membership.volunteer_credit"], true).map((tab) => tab.key)).toEqual(["volunteering"]);
    expect(communityMemberTabs(["membership.guest_passes"], false)).toEqual([]);
  });
});

describe("MinorsDesk", () => {
  const minor = { id: 6, user_id: 40, user_name: "Sam Young", age: 14, declared_under_age: false, guardian_user_id: null,
    guardian_name: "Pat Young", guardian_email: "pat@example.org", guardian_phone: "", consent_state: "none",
    consent_valid_until: null, consent_terms_version: null, current_consent_id: null, current_consent_version: null,
    current_consent_signed_at: null, cleared_at: null, created_at: "2026-11-01T00:00:00Z" };
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.includes("/minors?")) return page([minor]);
      if (path.endsWith("/guardian-terms") && !options?.method) return [{ id: 1, version: "v1", body: "I consent.", is_active: true, created_at: "2026-10-01T00:00:00Z", superseded_at: null }];
      if (path.endsWith("/consents")) return { id: 31, terms_version: "v1", method: "staff_recorded", signed_at: "2026-11-10T10:00:00Z", valid_until: "2027-11-10T10:00:00Z", revoked_at: null };
      return {};
    });
  });

  it("lists minors without a birth date, records a desk signature and can undo it", async () => {
    wrap(<MinorsDesk makerspaceId={3} canManageMakerspace />);
    expect(await screen.findByText("Sam Young")).toBeVisible();
    expect(screen.getByText(/Age 14/)).toBeVisible();
    expect(screen.getByText("Consent needed")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Revoke consent" })).toBeNull();
    expect(await screen.findByText("I consent.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Record desk signature" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByLabelText(/read and accepted/));
    fireEvent.click(within(dialog).getByRole("button", { name: "Record signature" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/minors/6/consents", expect.objectContaining({ method: "POST" })));
    fireEvent.click(await screen.findByRole("button", { name: "Undo: revoke this consent" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guardian-consents/31/revoke", { method: "POST", body: "{}" }));
  });

  it("shows the current consent and revokes it from the list after confirming", async () => {
    const signed = { ...minor, consent_state: "valid", consent_valid_until: "2027-10-01T00:00:00Z", consent_terms_version: "v1",
      current_consent_id: 27, current_consent_version: "v1", current_consent_signed_at: "2026-10-01T09:00:00Z" };
    vi.mocked(staffRequest).mockImplementation(async (path: string) => path.includes("/minors?") ? page([signed]) : path.endsWith("/guardian-terms") ? [] : {});
    wrap(<MinorsDesk makerspaceId={3} canManageMakerspace />);
    expect(await screen.findByText(/Current consent: version v1, signed/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Revoke consent" }));
    const dialog = await screen.findByRole("dialog");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspaces/3/guardian-consents/27/revoke", expect.anything());
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke consent" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guardian-consents/27/revoke", { method: "POST", body: "{}" }));
  });

  it("shows the consent history newest first and revokes any live consent after confirming", async () => {
    const base = { method: "staff_recorded", signer: "Pat Young", recorded_by_name: "Desk Staff", revoked_by_name: "" };
    const history = [
      { ...base, id: 40, terms_version: "v1", signed_at: "2026-09-01T09:00:00Z", valid_until: "2027-09-01T09:00:00Z", revoked_at: null, is_live: true },
      { ...base, id: 41, terms_version: "v2", signed_at: "2026-11-01T09:00:00Z", valid_until: "2027-11-01T09:00:00Z", revoked_at: null, is_live: true },
      { ...base, id: 39, terms_version: "v0", signed_at: "2025-01-01T09:00:00Z", valid_until: "2026-01-01T09:00:00Z", revoked_at: "2025-06-01T09:00:00Z", revoked_by_name: "Lee", is_live: false },
    ];
    vi.mocked(staffRequest).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.includes("/minors?")) return page([minor]);
      if (path.endsWith("/guardian-terms")) return [];
      if (path.endsWith("/minors/6/consents") && !options?.method) return history;
      return {};
    });
    wrap(<MinorsDesk makerspaceId={3} canManageMakerspace />);
    fireEvent.click(await screen.findByRole("button", { name: "Consent history" }));
    const list = await screen.findByRole("region", { name: "Consent history" });
    const items = await within(list).findAllByRole("listitem");
    expect(items.map((item) => within(item).getByText(/^Version/).textContent)).toEqual([
      expect.stringContaining("v2"), expect.stringContaining("v1"), expect.stringContaining("v0")]);
    expect(within(items[2]).getByText("Revoked by Lee")).toBeVisible();
    expect(within(items[2]).queryByRole("button", { name: "Revoke" })).toBeNull();
    expect(within(items[0]).getByText(/recorded by Desk Staff/)).toBeVisible();
    fireEvent.click(within(items[1]).getByRole("button", { name: "Revoke" }));
    const dialog = await screen.findByRole("dialog");
    expect(staffRequest).not.toHaveBeenCalledWith("/admin/makerspaces/3/guardian-consents/40/revoke", expect.anything());
    fireEvent.click(within(dialog).getByRole("button", { name: "Revoke consent" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/guardian-consents/40/revoke", { method: "POST", body: "{}" }));
  });

  it("records a minor by e-mail with an under-age declaration", async () => {
    wrap(<MinorsDesk makerspaceId={3} canManageMakerspace={false} />);
    expect(await screen.findByText("A Space Manager publishes new consent text.")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Record a minor" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Their e-mail or account number"), { target: { value: "kid@example.org" } });
    fireEvent.click(within(dialog).getByLabelText(/without a birth date/));
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/minors", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(vi.mocked(staffRequest).mock.calls.find(([path, options]) => String(path).endsWith("/minors") && options?.method === "POST")![1]!.body as string);
    expect(body).toMatchObject({ user_email: "kid@example.org", declared_under_age: true });
  });
});

describe("VolunteerQueue", () => {
  beforeEach(() => {
    vi.mocked(staffRequest).mockReset();
    vi.mocked(staffRequest).mockImplementation(async (path: string) => {
      if (path.includes("/volunteer-hours?")) return page([{ id: 2, member: 9, member_name: "Ada", minutes: 90, worked_on: "2026-11-08", description: "Tidied the shop", source: "manual", status: "pending", reviewed_at: null, review_note: "", created_at: "2026-11-08T00:00:00Z" }]);
      if (path.includes("/volunteer-credits?")) return page([{ id: 5, member: 9, member_name: "Ada Lovelace", kind: "discount", amount: "5.00", days: 0, currency: "EUR", status: "available", minutes_converted: 120, applied_payment: null, applied_amount: null, applied_at: null, created_at: "2026-11-01T00:00:00Z" }]);
      if (path.endsWith("/import-event-shifts")) return { created: 3 };
      return {};
    });
  });

  it("approves hours, imports shifts and voids a credit", async () => {
    wrap(<VolunteerQueue makerspaceId={3} />);
    expect(await screen.findByText("Ada")).toBeVisible();
    expect(screen.getByText(/1 h 30 min/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/volunteer-hours/2/decide", { method: "POST", body: JSON.stringify({ approve: true, note: "" }) }));
    fireEvent.click(screen.getByRole("button", { name: "Offer verified event shifts" }));
    expect(await screen.findByText(/3 shift entries added/)).toBeVisible();
    expect(await screen.findByText(/Ada Lovelace/)).toBeVisible();
    fireEvent.click(await screen.findByRole("button", { name: "Void" }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/3/volunteer-credits/5/void", { method: "POST", body: JSON.stringify({ reason: "" }) }));
  });
});
