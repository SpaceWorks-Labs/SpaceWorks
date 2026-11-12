import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PlatformChannelUsage } from "./PlatformChannelUsage";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest }));
afterEach(() => { cleanup(); staffRequest.mockReset(); });

const row = (makerspace_id: number | null, channel: string, value: number) => ({
  makerspace_id, period: "2026-11-01", measure: "session_days", channel, area: "all", value, share_percent: 50 });
const period = { start: "2026-11-01", end: "2026-11-30", grain: "month" };
const spaces = [{ id: 1, name: "Forge" }, { id: 2, name: "Loft" }] as never;
const mount = () => render(<QueryClientProvider client={new QueryClient()}>
  <PlatformChannelUsage period={period} spaces={spaces} /></QueryClientProvider>);

describe("PlatformChannelUsage", () => {
  it("asks the platform channel-usage report and drills into one space", async () => {
    staffRequest.mockResolvedValue({ meta: { definition: "Counts only." }, typed_rows: [
      row(1, "web", 6), row(1, "ios", 2), row(2, "android", 9), row(null, "web", 1)] });
    mount();
    const picker = await screen.findByLabelText("Drill into a space");
    expect(staffRequest.mock.calls[0][0]).toContain("/admin/platform/analytics/platform-channel-usage?");
    const names = Array.from(picker.querySelectorAll("option")).map(option => option.textContent);
    expect(names).toEqual(["Every space", "Forge", "Loft"]);
    fireEvent.change(picker, { target: { value: "2" } });
    expect((picker as HTMLSelectElement).value).toBe("2");
    const shares = screen.getByRole("region", { name: "Share of active sessions by channel" });
    await waitFor(() => expect(shares.textContent).toContain("100%"));
    expect(shares.textContent).toContain("Android");
  });

  it("offers no drill-down when the report has no rows", async () => {
    staffRequest.mockResolvedValue({ typed_rows: [] });
    mount();
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(screen.queryByLabelText("Drill into a space")).toBeNull();
  });
});
