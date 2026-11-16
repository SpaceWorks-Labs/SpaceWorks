import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
vi.mock("./analyticsApi", () => ({ useAnalyticsSummary: () => ({ error: new Error("offline"), data: undefined, isLoading: false }), useAnalyticsEmbed: () => ({}),
  usesMetabase: () => true, usesGrafana: () => false }));
vi.mock("./GrafanaViewer", () => ({ GrafanaViewer: () => null }));
vi.mock("./PublicFirebaseSettings", () => ({ PublicFirebaseSettings: () => <div>Platform Firebase editor</div> }));
vi.mock("./AnalyticsSettings", () => ({ AnalyticsSettings: () => null }));
vi.mock("./WebTelemetrySettings", () => ({ WebTelemetrySettings: () => null }));
import { AnalyticsPanel } from "./AnalyticsPanel";
it("keeps platform Firebase configuration available when Metabase is unavailable", () => {
  render(<AnalyticsPanel scope={{ kind: "platform" }} />); expect(screen.getByText("Platform Firebase editor")).toBeTruthy();
});
it("does not mount platform configuration for a makerspace", () => {
  render(<AnalyticsPanel scope={{ kind: "space", makerspaceId: 7 }} />); expect(screen.queryByText("Platform Firebase editor")).toBeNull();
  expect(screen.getByText(/Ask a platform administrator/)).toBeTruthy();
});
