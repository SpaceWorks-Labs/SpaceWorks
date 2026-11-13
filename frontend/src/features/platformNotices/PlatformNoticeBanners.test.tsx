import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { PlatformNoticeBanners } from "./PlatformNoticeBanners";
import { READ_ONLY_LEAD, type PlatformNotices } from "./platformNoticesApi";

const NOTICES: PlatformNotices = {
  announcements: [
    { id: 1, title: "Maintenance on Sunday", body: "Ten minutes of downtime.", severity: "maintenance", starts_at: "2026-11-01T00:00:00Z", ends_at: null, makerspace_ids: [] },
    { id: 2, title: "South Lab moves", body: "New address.", severity: "info", starts_at: "2026-11-01T00:00:00Z", ends_at: null, makerspace_ids: [8] },
  ],
  spaces: [{ id: 7, name: "North Lab", slug: "north-lab", state: "read_only", reason: "Trial ended on 1 November.", since: "2026-11-01T00:00:00Z" }],
};

beforeEach(() => { window.localStorage.clear(); });

describe("PlatformNoticeBanners", () => {
  it("shows every-space announcements and the read-only banner with its reason for this space", () => {
    render(<PlatformNoticeBanners data={NOTICES} space={{ id: 7 }} />);
    expect(screen.getByText("Maintenance on Sunday")).toBeInTheDocument();
    expect(screen.queryByText("South Lab moves")).not.toBeInTheDocument();
    expect(screen.getByText(READ_ONLY_LEAD)).toBeInTheDocument();
    expect(screen.getByText(/Trial ended on 1 November\./)).toBeInTheDocument();
  });

  it("matches the member's space by slug when its id is unknown", () => {
    render(<PlatformNoticeBanners data={NOTICES} space={{ slug: "north-lab" }} />);
    expect(screen.getByText(READ_ONLY_LEAD)).toBeInTheDocument();
  });

  it("shows no other space's announcements while this space's id is still loading (#195)", () => {
    render(<PlatformNoticeBanners data={NOTICES} space={{ slug: "unknown-yet" }} />);
    expect(screen.queryByText("South Lab moves")).not.toBeInTheDocument();
    expect(screen.queryByText("Maintenance on Sunday")).not.toBeInTheDocument();
  });

  it("shows no read-only banner for another space", () => {
    render(<PlatformNoticeBanners data={NOTICES} space={{ id: 8 }} />);
    expect(screen.queryByText(READ_ONLY_LEAD)).not.toBeInTheDocument();
    expect(screen.getByText("South Lab moves")).toBeInTheDocument();
  });

  it("remembers a dismissed announcement", () => {
    const { unmount } = render(<PlatformNoticeBanners data={NOTICES} space={{ id: 7 }} />);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss announcement: Maintenance on Sunday" }));
    expect(screen.queryByText("Maintenance on Sunday")).not.toBeInTheDocument();
    unmount();
    render(<PlatformNoticeBanners data={NOTICES} space={{ id: 7 }} />);
    expect(screen.queryByText("Maintenance on Sunday")).not.toBeInTheDocument();
    expect(JSON.parse(window.localStorage.getItem("spaceworks.platformNotices.dismissed") ?? "[]")).toEqual([1]);
  });

  it("renders nothing when there is nothing to say", () => {
    const { container } = render(<PlatformNoticeBanners data={{ announcements: [], spaces: [] }} space={{ id: 7 }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
