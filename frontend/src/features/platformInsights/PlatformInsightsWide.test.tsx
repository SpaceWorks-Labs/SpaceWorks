import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async (original) => ({ ...await original<object>(), staffRequest, getAccessToken: () => "token" }));

import { PlatformInsightsPage } from "./PlatformInsightsPage";

const base = { window: { starts_at: "2026-10-12T00:00:00Z", ends_at: "2026-11-11T00:00:00Z" }, growth: [], organizations: [],
  staff_mfa: { active: 4, enabled: 3, without_mfa: 1, adoption_percent: 75 }, outbox: [] };
const wide = {
  activity: { events_held: 12, registrations: 340, check_ins: 280, feedback_responses: 51, broadcasts_sent: 6,
    recent_broadcasts: [{ completed_at: "2026-11-10T18:00:00Z", audience_statuses: ["registered"], audience_attendance: "any" }] },
  security: { accounts_unverified: 9, accounts_with_passkey: 21, login_methods: [{ method: "google", accounts: 40 }, { method: "oidc", accounts: 5 }],
    sensitive_actions: [{ action: "auth.mfa_reset", count: 2 }], api_clients: { active: 3, revoked: 1, rotating: 1, unused_in_window: 0 } },
  storage: { total_bytes: 5 * 1024 * 1024 * 1024, spaces: 7, largest_bytes: [2 * 1024 * 1024 * 1024] },
};
const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><PlatformInsightsPage /></QueryClientProvider>);

beforeEach(() => { staffRequest.mockReset(); });

it("shows the activity, security and storage counts (parity A16)", async () => {
  staffRequest.mockResolvedValue({ ...base, ...wide });
  mount();
  expect(await screen.findByText("Events held")).toBeVisible();
  expect(screen.getByText("340")).toBeVisible();
  expect(screen.getByText("Signs in with Google")).toBeVisible();
  expect(screen.getByText("Signs in with Organisation sign-in (OIDC)")).toBeVisible();
  expect(screen.getByText("Two-step sign-in reset")).toBeVisible();
  expect(screen.getByText("5 GB")).toBeVisible();
  expect(screen.getByText("Sizes only; spaces are not named here.")).toBeVisible();
});

it("says the Events module is off when activity is null, and tolerates an older server", async () => {
  staffRequest.mockResolvedValue({ ...base, ...wide, activity: null });
  const view = mount();
  expect(await screen.findByText("The Events module is off on this platform.")).toBeVisible();
  view.unmount();
  staffRequest.mockResolvedValue(base);
  mount();
  expect(await screen.findByText("Notification outbox")).toBeVisible();
  expect(screen.queryByText("Security posture")).toBeNull();
});
