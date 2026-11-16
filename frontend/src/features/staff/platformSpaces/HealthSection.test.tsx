import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HealthSection } from "./HealthSection";
import type { HealthCard } from "./spacesApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest, publicV1Request: vi.fn() }));

function healthCard(overrides: Partial<HealthCard> = {}): HealthCard {
  return {
    id: 7, name: "North Lab", slug: "north-lab", public_code: "NL", state: "active", created_at: "2026-01-01T00:00:00Z",
    lifecycle_state: "active", archived_at: null, suspended: null, read_only: null, schedule: null,
    usage: { managed: true, resources: [] }, usage_peak_percent: 85, last_activity_at: "2026-11-01T00:00:00Z",
    backups: { last_backed_up_at: "2026-11-04T00:00:00Z", last_drill: { outcome: "passed", finished_at: "2026-10-01T00:00:00Z" } },
    security: { blocked_accounts: 2, locked_settings: 1 }, open_issues: 3, modules: ["events", "machines"],
    managers: [{ membership_id: 11, user_id: 5, name: "Ada", email: "ada@example.com" }],
    ...overrides,
  };
}

function setup(card: HealthCard) {
  staffRequest.mockImplementation(async (path: string) => {
    if (path.startsWith("/admin/platform/space-health")) return { count: 1, next: null, previous: null, results: [card] };
    return card;
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <HealthSection managedPlans={false} />
  </QueryClientProvider>);
}

async function openAction(name: RegExp) {
  const card = await screen.findByRole("article", { name: "North Lab" });
  fireEvent.click(within(card).getByRole("button", { name: "Manage" }));
  fireEvent.click(await screen.findByRole("menuitem", { name }));
  return screen.findByRole("dialog");
}

/** The latest mutation; list refetches after it are GETs and are skipped. */
function lastCall() {
  const call = staffRequest.mock.calls.filter(row => (row[1] as RequestInit | undefined)?.method === "POST").at(-1);
  if (!call) return { path: "", body: undefined, context: undefined };
  return { path: call[0] as string, body: JSON.parse((call[1] as RequestInit).body as string), context: call[2] };
}

const REASON = "Unpaid for three months running.";

beforeEach(() => { staffRequest.mockReset(); });

describe("HealthSection", () => {
  it("renders a health card with its usage peak, backups, security and managers", async () => {
    setup(healthCard());
    const card = await screen.findByRole("article", { name: "North Lab" });
    expect(within(card).getByText("Active")).toBeInTheDocument();
    expect(within(card).getByText(/85% · Near limit/)).toBeInTheDocument();
    expect(within(card).getByRole("progressbar", { name: "North Lab highest usage" })).toHaveAttribute("aria-valuenow", "85");
    expect(within(card).getByText("2 blocked · 1 locked")).toBeInTheDocument();
    expect(within(card).getByText("Passed")).toBeInTheDocument();
    expect(within(card).getByText("Ada")).toBeInTheDocument();
    expect(within(card).queryByText("Plan")).not.toBeInTheDocument();
    expect(staffRequest).toHaveBeenCalledWith("/admin/platform/space-health?page=1", {}, "platform");
  });

  it.each([
    [/^Suspend/, "suspend", true],
    [/^Make read-only/, "read-only", true],
    [/^Archive now/, "archive", false],
  ])("%s posts to %s (reason required: %s)", async (label, action, needsReason) => {
    setup(healthCard());
    const dialog = await openAction(label);
    const confirm = within(dialog).getAllByRole("button").find(button => button.getAttribute("type") === "submit")!;
    if (needsReason) {
      expect(confirm).toBeDisabled();
      fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: REASON } });
    }
    fireEvent.click(confirm);
    await waitFor(() => expect(lastCall().path).toBe(`/admin/platform/spaces/7/${action}`));
    expect(lastCall().body).toEqual(needsReason ? { reason: REASON } : {});
    expect(lastCall().context).toBe("platform");
  });

  it.each([
    [{ suspended: { at: "2026-11-01T00:00:00Z", reason: "x", by: "root" }, lifecycle_state: "suspended" as const, state: "suspended" as const }, /^Unblock/, "unsuspend"],
    [{ read_only: { at: "2026-11-01T00:00:00Z", reason: "x", source: "manual" as const, by: null }, state: "read_only" as const }, /^Lift read-only/, "read-only/lift"],
    [{ schedule: { archive_on: "2027-01-01T00:00:00Z", purge_due_at: null, purge_grace_days: 90, note: "", scheduled_by: null, scheduled_at: null, reminders_sent: [] }, state: "scheduled" as const }, /^Cancel schedule/, "schedule/cancel"],
    [{ archived_at: "2026-10-01T00:00:00Z", state: "archived" as const }, /^Unarchive/, "unarchive"],
  ])("offers the inverse control on a changed space (%#)", async (overrides, label, action) => {
    setup(healthCard(overrides));
    const dialog = await openAction(label);
    fireEvent.click(within(dialog).getAllByRole("button").find(button => button.getAttribute("type") === "submit")!);
    await waitFor(() => expect(lastCall().path).toBe(`/admin/platform/spaces/7/${action}`));
    expect(lastCall().body).toEqual({});
  });

  it("transfers ownership with the previous manager's kept roles", async () => {
    setup(healthCard());
    const dialog = await openAction(/^Transfer ownership/);
    const submit = within(dialog).getByRole("button", { name: "Transfer ownership" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "New manager's email" }), { target: { value: "grace@example.com" } });
    expect(submit).toBeDisabled();
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Event Manager" }));
    fireEvent.click(submit);
    await waitFor(() => expect(lastCall().path).toBe("/admin/platform/spaces/7/transfer-ownership"));
    expect(lastCall().body).toEqual({ email: "grace@example.com", previous_membership_id: 11, previous_outcome: "keep_staff", previous_roles: ["event_manager"] });
  });

  it("sends no roles when the previous manager is revoked", async () => {
    setup(healthCard());
    const dialog = await openAction(/^Transfer ownership/);
    fireEvent.change(within(dialog).getByRole("textbox", { name: "New manager's email" }), { target: { value: "grace@example.com" } });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Remove their staff access" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Transfer ownership" }));
    await waitFor(() => expect(lastCall().body).toMatchObject({ previous_outcome: "revoke", previous_roles: [] }));
  });

  it("schedules an archive in the future with the default 90-day grace", async () => {
    setup(healthCard());
    const dialog = await openAction(/^Schedule archive & purge/);
    const submit = within(dialog).getByRole("button", { name: "Schedule" });
    expect(submit).toBeDisabled();
    const input = dialog.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    fireEvent.change(input, { target: { value: "2099-01-15T10:00" } });
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Type north-lab to confirm" }), { target: { value: "north-lab" } });
    fireEvent.click(submit);
    await waitFor(() => expect(lastCall().path).toBe("/admin/platform/spaces/7/schedule"));
    expect(lastCall().body).toMatchObject({ purge_grace_days: 90, note: "", confirm_slug: "north-lab" });
    expect(lastCall().body.archive_on).toMatch(/^2099-01-15T/);
  });

  it("schedules the purge of an archived space without an archive date", async () => {
    setup(healthCard({ archived_at: "2026-10-01T00:00:00Z", state: "archived" }));
    const dialog = await openAction(/^Schedule purge/);
    expect(dialog.querySelector('input[type="datetime-local"]')).toBeNull();
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Type north-lab to confirm" }), { target: { value: "north-lab" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Schedule purge" }));
    await waitFor(() => expect(lastCall().body).toEqual({ archive_on: null, purge_grace_days: 90, note: "", confirm_slug: "north-lab" }));
  });

  it("purges only after the slug is typed out", async () => {
    setup(healthCard({ archived_at: "2026-10-01T00:00:00Z", state: "archived" }));
    const dialog = await openAction(/^Purge/);
    const submit = within(dialog).getByRole("button", { name: "Purge for good" });
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "north" } });
    expect(submit).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "north-lab" } });
    fireEvent.click(submit);
    await waitFor(() => expect(lastCall()).toMatchObject({ path: "/admin/platform/spaces/7/purge", body: { confirm_slug: "north-lab" } }));
  });

  it("does not offer purge on a live space", async () => {
    setup(healthCard());
    fireEvent.click(within(await screen.findByRole("article", { name: "North Lab" })).getByRole("button", { name: "Manage" }));
    expect(screen.queryByRole("menuitem", { name: /^Purge/ })).not.toBeInTheDocument();
  });

  it("shows the server's refusal in the dialog", async () => {
    setup(healthCard());
    const dialog = await openAction(/^Archive now/);
    const { StructuredApiError } = await import("../../../lib/api/errors");
    staffRequest.mockRejectedValueOnce(new StructuredApiError(409, { detail: "This space is not active.", code: "space_not_active" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Archive now" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("This space is not active.");
  });
});
