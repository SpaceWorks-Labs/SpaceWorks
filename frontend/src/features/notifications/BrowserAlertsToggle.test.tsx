import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const staffRequest = vi.fn();
vi.mock("../../lib/api", async (importOriginal) => ({ ...(await importOriginal<object>()), staffRequest: (path: string) => staffRequest(path) }));

import { BrowserAlertsToggle } from "./BrowserAlertsToggle";

describe("BrowserAlertsToggle", () => {
  beforeEach(() => {
    vi.stubGlobal("PushManager", function PushManager() {});
    vi.stubGlobal("Notification", function Notification() {});
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { getRegistration: vi.fn(async () => undefined) } });
  });
  afterEach(() => { vi.unstubAllGlobals(); staffRequest.mockReset(); });

  it("does not ask for the per-space state when the deployment has no push key", async () => {
    staffRequest.mockResolvedValue({ configured: false, public_key: "" });
    const { container } = render(<BrowserAlertsToggle makerspaceId={4} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/notifications/browser-alerts/key"));
    expect(staffRequest).not.toHaveBeenCalledWith("/notifications/browser-alerts/4");
    expect(container.textContent).toBe("");
  });

  it("reads the per-space state once a key is configured", async () => {
    staffRequest.mockImplementation(async (path: string) => path.endsWith("/key")
      ? { configured: true, public_key: "BPublic" } : { subscribed_browsers: 0 });
    render(<BrowserAlertsToggle makerspaceId={4} />);
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/notifications/browser-alerts/4"));
  });
});
