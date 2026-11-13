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
    staffRequest.mockResolvedValueOnce({ meta: { definition: "Counts only.", space_ids: [1, 2] }, typed_rows: [
      row(1, "web", 6), row(1, "ios", 2), row(2, "android", 9), row(null, "web", 1)] });
    staffRequest.mockResolvedValue({ typed_rows: [row(2, "android", 12)] });
    mount();
    const picker = await screen.findByLabelText("Drill into a space");
    expect(staffRequest.mock.calls[0][0]).toContain("/admin/platform/analytics/platform-channel-usage?");
    const names = Array.from(picker.querySelectorAll("option")).map(option => option.textContent);
    expect(names).toEqual(["Every space", "Forge", "Loft"]);
    fireEvent.change(picker, { target: { value: "2" } });
    expect((picker as HTMLSelectElement).value).toBe("2");
    const shares = await screen.findByRole("region", { name: "Share of active sessions by channel" });
    await waitFor(() => expect(shares.textContent).toContain("100%"));
    expect(shares.textContent).toContain("Android");
    expect(shares.textContent).toContain("12 active session-days");
    expect(staffRequest.mock.calls[1][0]).toContain("/admin/platform/analytics/makerspaces/2/analytics/channel-usage?");
  });

  it("offers a space whose shared sessions were attributed elsewhere in the platform total", async () => {
    staffRequest.mockResolvedValueOnce({ meta: { space_ids: [1, 2] }, typed_rows: [row(1, "web", 1)] });
    staffRequest.mockResolvedValue({ typed_rows: [row(2, "web", 1)] });
    mount();
    const picker = await screen.findByLabelText("Drill into a space");
    expect(picker.querySelector('option[value="2"]')).toHaveTextContent("Loft");
    fireEvent.change(picker, { target: { value: "2" } });
    expect(await screen.findByText("1 active session-days")).toBeVisible();
    await waitFor(() => expect(staffRequest).toHaveBeenCalledTimes(2));
  });

  it("offers no drill-down when the report has no rows", async () => {
    staffRequest.mockResolvedValue({ typed_rows: [] });
    mount();
    await waitFor(() => expect(staffRequest).toHaveBeenCalled());
    expect(screen.queryByLabelText("Drill into a space")).toBeNull();
  });
});
