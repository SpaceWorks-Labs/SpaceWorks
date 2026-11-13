import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuditLog } from "./AuditLog";
import { AUDIT_AREAS, AUDIT_READER_ACTIONS, auditAreasFor, canReadAudit } from "./auditAreas";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));

vi.mock("../../../lib/api", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/api")>("../../../lib/api");
  return { ...actual, staffRequest };
});

// Effective actions of the fixed roles (staffAccess.roleMatrix.test.ts holds the full sets).
const INVENTORY_MANAGER = ["accept_request", "assign_box", "edit_inventory", "issue_direct_loan", "issue_request",
  "manage_qr", "reject_request", "return_request", "upload_evidence", "view_audit", "view_inventory"];

function renderPanel(actions?: readonly string[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}>
    <AuditLog makerspaceId={7} actions={actions} />
  </QueryClientProvider></MemoryRouter>);
}

function openFilters() {
  const trigger = screen.queryByRole("button", { name: /^Filters/ });
  if (trigger) fireEvent.click(trigger);
}

describe("auditAreasFor (#219e)", () => {
  it("gives the Space Manager and the superadmin the whole space", () => {
    expect(auditAreasFor(undefined)).toBeNull();
    expect(auditAreasFor(["view_audit", "manage_makerspace"])).toBeNull();
  });

  it("opens only the areas a role's actions name", () => {
    expect(auditAreasFor(INVENTORY_MANAGER)).toEqual(["lending", "handover", "repairs"]);
    expect(auditAreasFor(["view_audit", "manage_machines"])).toEqual(["machines", "repairs"]);
    expect(auditAreasFor(["view_audit", "manage_events"])).toEqual(["events"]);
    expect(auditAreasFor(["view_audit", "manage_shop", "sell_shop", "view_shop"])).toEqual(["shop"]);
    expect(auditAreasFor(["view_audit", "work_repairs"])).toEqual(["repairs"]);
    // A bare audit grant opens no area: money, people and settings stay the Space Manager's.
    expect(auditAreasFor(["view_audit"])).toEqual([]);
    expect(AUDIT_AREAS).toHaveLength(11);
  });
});

describe("canReadAudit (#219 e-1)", () => {
  it("admits area readers without view_audit and keeps the handover desk out", () => {
    // Twin: backend apps/audit/areas.py READER_ACTIONS.
    expect([...AUDIT_READER_ACTIONS].sort()).toEqual(["accept_request", "edit_inventory", "manage_bookings",
      "manage_donations", "manage_events", "manage_machines", "manage_makerspace", "manage_members", "manage_printing", "manage_qr",
      "manage_shop", "reject_request", "run_maintenance", "set_service_state", "view_finance", "work_repairs"]);
    for (const actions of [["manage_machines"], ["manage_events"], ["manage_bookings"], ["manage_shop", "sell_shop", "view_shop"],
      ["work_repairs", "run_maintenance", "set_service_state"], ["view_audit"]]) expect(canReadAudit(actions), actions.join()).toBe(true);
    expect(canReadAudit(["assign_box", "collect_service_request", "issue_direct_loan", "issue_request", "return_request",
      "upload_evidence", "view_inventory"])).toBe(false);
    expect(canReadAudit([])).toBe(false);
  });
});

describe("AuditLog area narrowing", () => {
  beforeEach(() => {
    staffRequest.mockReset();
    staffRequest.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it("offers only the reader's areas and says the trail is narrowed", async () => {
    renderPanel(INVENTORY_MANAGER);
    expect(await screen.findByText("No audit entries in your areas yet.")).toBeTruthy();
    expect(screen.getByText(/State changes in the areas you work in/)).toBeTruthy();
    openFilters();
    const select = screen.getByLabelText("Area") as HTMLSelectElement;
    expect([...select.options].map(option => option.value)).toEqual(["", "lending", "handover", "repairs"]);
    fireEvent.change(select, { target: { value: "lending" } });
    await waitFor(() => expect(staffRequest.mock.calls.some(([path]) => String(path).includes("area=lending"))).toBe(true));
  });

  it("lets an area reader without view_audit read rows but not start verification (#219 e-1)", async () => {
    renderPanel(["manage_events"]);
    expect(await screen.findByText("No audit entries in your areas yet.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Verify these entries" })).toBeNull();
  });

  it("keeps the full trail copy and every area for the Space Manager", async () => {
    renderPanel(["view_audit", "manage_makerspace"]);
    expect(await screen.findByText("No audit entries yet. Complete a workflow to start the trail.")).toBeTruthy();
    openFilters();
    expect((screen.getByLabelText("Area") as HTMLSelectElement).options).toHaveLength(AUDIT_AREAS.length + 1);
  });
});
