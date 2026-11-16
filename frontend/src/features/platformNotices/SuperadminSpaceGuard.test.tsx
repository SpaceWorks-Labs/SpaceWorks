import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSuperadminAcknowledgements, SuperadminSpaceGuard, superadminWarning, superadminWriteGuard } from "./SuperadminSpaceGuard";
import { applicableAnnouncements } from "./PlatformNoticeBanners";
import { setStaffWriteGuard, staffRequest } from "../../lib/api/requests";
import type { NoticeSpace, PlatformNotices } from "./platformNoticesApi";

const READ_ONLY: NoticeSpace = { id: 7, name: "North Lab", slug: "north-lab", state: "read_only", reason: "Invoice overdue.", since: "2026-11-01T00:00:00Z" };

beforeEach(() => resetSuperadminAcknowledgements());
afterEach(() => setStaffWriteGuard(null));

describe("superadmin in a paused or read-only space (#195)", () => {
  it("shows a clear warning banner", () => {
    render(<SuperadminSpaceGuard notice={READ_ONLY} />);
    expect(screen.getByRole("alert")).toHaveTextContent(superadminWarning(READ_ONLY));
    expect(superadminWarning({ ...READ_ONLY, state: "suspended" })).toContain("which is paused");
  });

  it("confirms before the first write, then remembers it, and never asks for platform controls", () => {
    const confirm = vi.fn(() => true);
    const guard = superadminWriteGuard(READ_ONLY, confirm);
    expect(guard("/admin/platform/spaces/7/read-only/lift")).toBe(true);
    expect(confirm).not.toHaveBeenCalled();
    expect(guard("/admin/makerspace/7/consumables")).toBe(true);
    expect(guard("/admin/makerspace/7/consumables")).toBe(true);
    expect(confirm).toHaveBeenCalledTimes(1);
  });

  it("a declined confirm cancels the request before it is sent", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    setStaffWriteGuard(superadminWriteGuard(READ_ONLY, () => false));
    await expect(staffRequest("/admin/makerspace/7/consumables", { method: "POST", body: "{}" })).rejects.toMatchObject({ status: 409 });
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});

describe("announcements on member pages are limited to the viewer's member spaces", () => {
  const data: PlatformNotices = { spaces: [], announcements: [
    { id: 1, title: "Staff only", body: "", severity: "info", starts_at: "", ends_at: null, makerspace_ids: [7], member_makerspace_ids: [] },
    { id: 2, title: "Members too", body: "", severity: "info", starts_at: "", ends_at: null, makerspace_ids: [7, 8], member_makerspace_ids: [8] },
  ] };

  it("member pages without a space show only member-reaching announcements", () => {
    expect(applicableAnnouncements(data, undefined, "member").map(row => row.id)).toEqual([2]);
  });

  it("member pages of a space show only that space's", () => {
    expect(applicableAnnouncements(data, 7, "member")).toEqual([]);
    expect(applicableAnnouncements(data, 8, "member").map(row => row.id)).toEqual([2]);
  });

  it("staff pages keep the staff reach", () => {
    expect(applicableAnnouncements(data, 7).map(row => row.id)).toEqual([1, 2]);
  });
});
