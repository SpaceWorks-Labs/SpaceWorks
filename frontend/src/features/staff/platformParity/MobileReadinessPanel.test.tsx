import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { staffRequest } from "../../../lib/api";
import { MobileReadinessPanel } from "./MobileReadinessPanel";

vi.mock("../../../lib/api", async importOriginal => ({ ...(await importOriginal<typeof import("../../../lib/api")>()), staffRequest: vi.fn() }));
const request = vi.mocked(staffRequest);
const check = (ready: boolean, hint: string) => ({ ready, hint });
const readiness = { platforms: {
  android: { hint: "All production registrations must be ready.", login_ready: false, push_ready: false, apple_revocation_ready: false,
    associations_ready: true, registrations: [{ hint: "", production: true, login_ready: false,
      login: { registration: check(true, "ok"), attestation: check(false, "Configure a Play Integrity service account.") },
      optional: { push: check(false, "Add FCM credentials.") } }] },
  ios: { hint: "All production registrations must be ready.", login_ready: false, push_ready: false, apple_revocation_ready: false,
    associations_ready: false, registrations: [] },
} };

describe("MobileReadinessPanel (#190 parity)", () => {
  beforeEach(() => { request.mockReset(); request.mockResolvedValue(readiness as never); });

  it("reads the platform readiness route and lists only the failing checks with their hints", async () => {
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MobileReadinessPanel /></QueryClientProvider>);
    expect(await screen.findByText("Android")).toBeInTheDocument();
    expect(request).toHaveBeenCalledWith("/admin/platform/mobile-readiness", {}, "platform");
    expect(screen.getByText(/Configure a Play Integrity service account/)).toBeInTheDocument();
    expect(screen.getByText(/Add FCM credentials/)).toBeInTheDocument();
    expect(screen.getByText("App links: ready")).toBeInTheDocument();
    expect(screen.getByText("No approved registration for this platform yet.")).toBeInTheDocument();
    expect(screen.queryByText(/^registration:/)).not.toBeInTheDocument();
  });
});
