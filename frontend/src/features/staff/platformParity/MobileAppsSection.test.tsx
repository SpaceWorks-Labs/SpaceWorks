import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { SpaceChatTemplates } from "../SpaceChatTemplates";
import { MobileAppsSection } from "./MobileAppsSection";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const app = { id: 3, makerspace: null, app_id: "org.spaceworks.app", platform: "android", environment: "production",
  verifier_config_key: "default", signing_identities: ["AB:CD"], min_supported_version: null, status: "approved",
  approved_by: "root", revoked_at: null, created_at: "2026-11-01T10:00:00Z", updated_at: "2026-11-01T10:00:00Z" };

function renderWith(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("MobileAppsSection", () => {
  beforeEach(() => { request.mockReset(); request.mockImplementation(async (_path, init) => (init?.method ? app : page([app])) as never); });

  it("lists apps and revokes through the edit form", async () => {
    renderWith(<MobileAppsSection />);
    expect(await screen.findByText("org.spaceworks.app")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Edit org.spaceworks.app" }));
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "revoked" } });
    fireEvent.click(screen.getByRole("button", { name: "Save app" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith("/admin/platform/native-apps/3",
      expect.objectContaining({ method: "PATCH", body: expect.stringContaining("\"status\":\"revoked\"") }), "platform"));
  });
});

describe("SpaceChatTemplates", () => {
  beforeEach(() => { request.mockReset(); request.mockImplementation(async () => page([]) as never); });

  it("loads the space's own templates through the space path, not the platform one", async () => {
    renderWith(<SpaceChatTemplates makerspace={{ id: 5, name: "North Lab" }} />);
    fireEvent.click(screen.getByRole("button", { name: /Chat templates/ }));
    expect(await screen.findByText("North Lab uses the built-in text for every event.")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/makerspace/5/chat-templates?page=1", {});
  });
});
