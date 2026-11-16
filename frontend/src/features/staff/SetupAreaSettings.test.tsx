import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { staffRequest } from "../../lib/api";
import { EventDefaultsSettings } from "./EventDefaultsSettings";
import { NotificationTimingSettings } from "./NotificationTimingSettings";
import { BorrowRequestAccessSettings } from "./BorrowRequestAccessSettings";

vi.mock("../../lib/api", () => ({ staffRequest: vi.fn() }));
beforeEach(() => vi.clearAllMocks());

it("changes the new-event audience and refreshes event creation defaults", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ event_default_registration_audience: "accounts", enabled_features: [] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  render(<QueryClientProvider client={client}><EventDefaultsSettings makerspaceId={7} /></QueryClientProvider>);
  const audience = await screen.findByRole("combobox", { name: "Default registration audience" });
  await waitFor(() => expect(audience).toHaveValue("accounts"));
  fireEvent.change(audience, { target: { value: "invite" } });
  vi.mocked(staffRequest).mockResolvedValue({ event_default_registration_audience: "invite", enabled_features: [] });
  fireEvent.click(screen.getByRole("button", { name: "Save event defaults" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7", {
    method: "PATCH", body: JSON.stringify({ event_default_registration_audience: "invite" }),
  }));
  await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: ["events", 7] }));
});

it("allows a manager to change the daily digest default without a signing secret", async () => {
  const policy = { quiet_start: "22:00:00", quiet_end: "08:00:00", digest_at: "08:00:00", channels: ["email"], daily_digest_default: false, bounce_configured: true };
  vi.mocked(staffRequest).mockResolvedValue(policy);
  render(<QueryClientProvider client={new QueryClient()}><NotificationTimingSettings makerspaceId={7} timezone="Asia/Kolkata" /></QueryClientProvider>);
  const control = await screen.findByRole("checkbox", { name: "Daily digests on by default" });
  fireEvent.click(control);
  // The revamp's settings editors show the shared Save changes / Discard bar once a field is dirty.
  fireEvent.click(await screen.findByRole("button", { name: "Save changes" }));
  await waitFor(() => expect(staffRequest).toHaveBeenCalledWith("/integrations/makerspace/7/timing-policy", {
    method: "PATCH", body: JSON.stringify({ quiet_start: policy.quiet_start, quiet_end: policy.quiet_end, digest_at: policy.digest_at, channels: ["email"], daily_digest_default: true }),
  }));
});

// r1-security (#75f): every borrow request needs a signed-in account, so the "Who can submit borrow
// requests?" picker and its anonymous_requests_enabled PATCH are gone. The row now only states the
// server's policy; the assertions about the removed control are retired.
it("states account-only borrowing read-only and never offers account-less requests", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ request_access: "accounts" });
  render(<QueryClientProvider client={new QueryClient()}><BorrowRequestAccessSettings makerspaceId={7} /></QueryClientProvider>);
  expect(await screen.findByText("Anyone with a signed-in account")).toBeInTheDocument();
  expect(staffRequest).toHaveBeenCalledWith("/admin/makerspaces/7");
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Anyone, no account" })).not.toBeInTheDocument();
  expect(vi.mocked(staffRequest).mock.calls.some(([, options]) => options?.method === "PATCH")).toBe(false);
});

it("shows the server's members-only policy as fixed while Membership is enabled", async () => {
  vi.mocked(staffRequest).mockResolvedValue({ request_access: "members" });
  render(<QueryClientProvider client={new QueryClient()}><BorrowRequestAccessSettings makerspaceId={7} /></QueryClientProvider>);
  expect(await screen.findByText("Active members only")).toBeInTheDocument();
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "Anyone, no account" })).not.toBeInTheDocument();
});
