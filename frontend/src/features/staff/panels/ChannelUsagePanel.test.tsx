import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChannelUsagePanel } from "./ChannelUsagePanel";

const rows = [
  { makerspace_id: 1, period: "2026-11-01", measure: "session_days", channel: "web", area: "all", value: 6, share_percent: 75 },
  { makerspace_id: 1, period: "2026-11-01", measure: "session_days", channel: "ios", area: "all", value: 2, share_percent: 25 },
  { makerspace_id: 1, period: "2026-11-01", measure: "api_calls", channel: "web", area: "events", value: 40, share_percent: 100 },
];

describe("ChannelUsagePanel", () => {
  it("shows the channel split, the per-space table and the top features", () => {
    render(<ChannelUsagePanel rows={rows} spaceName={id => `Space ${id}`} meta={{ definition: "Counts only." }} />);
    expect(screen.getByText("75%")).toBeTruthy();
    expect(screen.getByText("25%")).toBeTruthy();
    expect(screen.getByText("Counts only.")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Top features by channel" }).textContent).toContain("40");
    expect(screen.getAllByText("Space 1").length).toBeGreaterThan(0);
  });
  it("explains an empty period instead of drawing nothing", () => {
    render(<ChannelUsagePanel rows={[]} />);
    expect(screen.queryByText("75%")).toBeNull();
  });
});
