import { describe, expect, it } from "vitest";
import { accountTotals, appVersions, channelCsv, channelTotals, flowShares, forSpace, perSpace, topAreas, trendRows } from "./channelUsage";
import { reportFieldLabel } from "./reportFieldLabels";

const rows = [
  { makerspace_id: 1, period: "2026-11-01", measure: "session_days", channel: "web", area: "all", value: 6, share_percent: 75 },
  { makerspace_id: 1, period: "2026-11-01", measure: "session_days", channel: "ios", area: "all", value: 2, share_percent: 25 },
  { makerspace_id: null, period: "2026-11-02", measure: "session_days", channel: "web", area: "all", value: 2, share_percent: 100 },
  { makerspace_id: 1, period: "2026-11-01", measure: "api_calls", channel: "web", area: "events", value: 40, share_percent: 80 },
  { makerspace_id: 1, period: "2026-11-01", measure: "api_calls", channel: "web", area: "bookings", value: 10, share_percent: 20 },
  { makerspace_id: 1, period: "2026-11-01", measure: "active_accounts", channel: "web", area: "all", value: 5, share_percent: 100 },
  { makerspace_id: 1, period: "2026-11-01", measure: "new_accounts", channel: "web", area: "all", value: 2, share_percent: 100 },
  { makerspace_id: 1, period: "2026-11-01", measure: "returning_accounts", channel: "web", area: "all", value: 3, share_percent: 100 },
  { makerspace_id: 1, period: "2026-11-01", measure: "flow_completions", channel: "web", area: "booking_made", value: 3, share_percent: 75 },
  { makerspace_id: 1, period: "2026-11-01", measure: "flow_completions", channel: "ios", area: "booking_made", value: 1, share_percent: 25 },
  { makerspace_id: 1, period: "2026-11-01", measure: "app_versions", channel: "ios", area: "2.1.0", value: 3, share_percent: 75 },
  { makerspace_id: 1, period: "2026-11-01", measure: "app_versions", channel: "ios", area: "unknown", value: 1, share_percent: 25 },
  { makerspace_id: 1, period: "2026-11-01", measure: "api_calls", channel: "api_client", area: "inventory", value: 7, share_percent: 100 },
];

describe("channel usage projections", () => {
  it("splits session-days by channel in a fixed order with shares", () => {
    expect(channelTotals(rows, "session_days")).toEqual([
      { channel: "web", total: 8, share: 80 }, { channel: "ios", total: 2, share: 20 },
    ]);
  });
  it("makes one trend point per period and channel", () => {
    expect(trendRows(rows)).toEqual([
      { period: "2026-11-01", channel: "web", value: 6 }, { period: "2026-11-01", channel: "ios", value: 2 },
      { period: "2026-11-02", channel: "web", value: 2 },
    ]);
  });
  it("tallies per space, naming unattributed activity, and skips rows without a space column", () => {
    const table = perSpace(rows, id => id == null ? "Deployment" : `Space ${id}`);
    expect(table.map(row => [row.name, row.total])).toEqual([["Space 1", 8], ["Deployment", 2]]);
    expect(perSpace(rows.map(({ makerspace_id: _ignored, ...rest }) => rest), () => "x")).toEqual([]);
  });
  it("ranks the busiest areas per channel by calls", () => {
    expect(topAreas(rows)).toEqual([
      { channel: "web", areas: [{ area: "events", value: 40 }, { area: "bookings", value: 10 }] },
      { channel: "api_client", areas: [{ area: "inventory", value: 7 }] },
    ]);
  });
  it("projects accounts, flows and app builds and exports CSV without identifiers", () => {
    expect(accountTotals(rows)).toEqual([{ channel: "web", active: 5, fresh: 2, returning: 3 }]);
    expect(flowShares(rows)[0]).toMatchObject({ flow: "booking_made", total: 4, channels: [{ channel: "web", share: 75 }, { channel: "ios", share: 25 }] });
    expect(appVersions(rows)[0].versions.map(v => v.version)).toEqual(["2.1.0", "unknown"]);
    expect(forSpace(rows, 1).every(row => row.makerspace_id === 1)).toBe(true);
    expect(channelCsv(forSpace(rows, 1)).split(/\r?\n/)[0]).toBe("makerspace_id,period,measure,channel,area,value,share_percent");
  });
  it("labels the new report fields and the split app-session metric", () => {
    expect(reportFieldLabel("window_hours")).toBe("Window hours");
    expect(reportFieldLabel("active_app_sessions")).toBe("Active app sessions");
    expect(reportFieldLabel("active_web_sessions")).toBe("Active web sessions");
    expect(reportFieldLabel("share_percent")).toBe("Share (%)");
  });
});
