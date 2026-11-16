import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TELEMETRY_DOCS_URL, TelemetryProviderHelp, telemetryProviderHelp } from "./TelemetryProviderHelp";

describe("TelemetryProviderHelp (A213)", () => {
  it("names the operator allow-list for GA4 and Clarity and links the provider guide", () => {
    expect(telemetryProviderHelp("ga4")).toContain("WEB_TELEMETRY_ALLOWED_ORIGINS");
    expect(telemetryProviderHelp("clarity")).toContain("WEB_TELEMETRY_ALLOWED_ORIGINS");
    render(<TelemetryProviderHelp provider="umami" />);
    expect(screen.getByRole("link", { name: /Provider guide/ })).toHaveAttribute("href", TELEMETRY_DOCS_URL);
  });

  it("says nothing for no provider", () => {
    const { container } = render(<TelemetryProviderHelp provider="none" />);
    expect(container).toBeEmptyDOMElement();
  });
});
