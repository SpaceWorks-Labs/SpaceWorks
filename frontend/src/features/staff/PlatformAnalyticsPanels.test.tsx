import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { platformChartRows } from "./PlatformAnalyticsPanels";
import { PLATFORM_CHART_SPECS } from "./platformAnalyticsApi";
import { AnalyticsData } from "./panels/AnalyticsData";
import { toChartData } from "./panels/charts/chartSpec";
import { wireChartSpec } from "./panels/charts/wireChartSpec";

afterEach(cleanup);

describe("platform SMS purpose projection", () => {
  it("keeps OTP and notification rows distinct in both charts and tables", () => {
    const base = { makerspace_id: 11, day: "2026-10-17", service: "sms", provider_source: "platform",
      status: "sent", bucket: "visible", count: 3 };
    const rows = platformChartRows([{ ...base, purpose: "otp" }, { ...base, purpose: "notification" }]);
    const spec = PLATFORM_CHART_SPECS["platform-services"];
    const data = toChartData(wireChartSpec(spec, "stacked_bar", rows), rows);
    expect(data.series).toHaveLength(2);
    expect(data.series.map(series => series.points[0].value)).toEqual([3, 3]);
    render(<AnalyticsData title="Platform services" rows={rows} spec={spec} hint="stacked_bar" />);
    fireEvent.click(screen.getByRole("button", { name: "Show report data" }));
    expect(screen.getByRole("columnheader", { name: "Purpose" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "otp" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "notification" })).toBeInTheDocument();
  });

  it("names every makerspace row and drops the raw makerspace id", () => {
    expect(platformChartRows([{ makerspace_id: 99, purpose: "otp", status: "failed", provider_source: "platform",
      bucket: "makerspace", day: "2026-10-17", service: "sms", count: 7 }], [{ id: 99, name: "Forge", slug: "forge" }])).toEqual([
      { makerspace: "Forge", purpose: "otp", status: "failed", provider_source: "platform",
        bucket: "makerspace", day: "2026-10-17", service: "sms", count: 7 },
    ]);
  });
});
