import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AccountsSection, FlowsSection, VersionsSection } from "./ChannelUsageSections";

afterEach(cleanup);

describe("ChannelUsageSections", () => {
  it("says so when a section has nothing to show", () => {
    render(<><AccountsSection items={[]} /><FlowsSection items={[]} /><VersionsSection items={[]} /></>);
    expect(screen.getByText("No active accounts recorded in this period.")).toBeTruthy();
    expect(screen.getByText("No completed flows recorded in this period.")).toBeTruthy();
    expect(screen.getByText(/No app builds reported/)).toBeTruthy();
  });

  it("shows accounts, flow shares and app versions as counts only", () => {
    render(<>
      <AccountsSection items={[{ channel: "ios", active: 5, fresh: 2, returning: 3 }]} />
      <FlowsSection items={[{ flow: "checkout", total: 10, channels: [{ channel: "web", value: 6, share: 60 }, { channel: "ios", value: 4, share: 40 }] }]} />
      <VersionsSection items={[{ channel: "android", versions: [{ version: "1.2.0", value: 3, share: 75 }, { version: "unknown", value: 1, share: 25 }] }]} />
    </>);
    expect(screen.getByRole("region", { name: "Active accounts by channel" }).textContent).toContain("5");
    expect(screen.getByRole("region", { name: "Key flows by channel" }).textContent).toMatch(/60%/);
    const versions = screen.getByRole("region", { name: "App versions" });
    expect(versions.textContent).toContain("1.2.0");
    expect(versions.textContent).toContain("Unknown");
  });
});
