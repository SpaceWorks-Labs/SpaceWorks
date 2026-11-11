import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StructuredApiError } from "../../../lib/api";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async (original) => ({ ...await original<object>(), staffRequest, memberRequest: vi.fn() }));

import { StaffClaimForm, staffClaimError } from "./StaffClaimForm";

const scope = { actorId: 1, makerspaceId: 2, eventId: 3 };
const programme = { initialized: true, id: 8, version: 1, currency: "usd", finance_policy_revision: 1, allowed_categories: ["rail", "lodging"],
  pools: [{ id: 1, version: 1, currency: "usd", total_minor: 50000, available_minor: 40000, reserved_minor: 0, committed_minor: 10000, audience: "participants" },
    { id: 2, version: 1, currency: "usd", total_minor: 20000, available_minor: 15000, reserved_minor: 0, committed_minor: 5000, audience: "crew" }] };
const wrap = (ui: JSX.Element) => <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{ui}</QueryClientProvider>;

beforeEach(() => {
  staffRequest.mockReset();
  staffRequest.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.endsWith("/programme/")) return programme;
    if (path.includes("/registrations/")) return { results: [{ id: 70, name: "Asha (speaker)", status: "registered" }, { id: 71, name: "Gone", status: "cancelled" }] };
    if (options?.method === "POST") return { id: 99, version: 0, state: "requested" };
    throw new Error(`unexpected ${path}`);
  });
});

describe("staff expense claims (parity C17)", () => {
  it("files a claim on behalf of a speaker with an idempotency key", async () => {
    const onFiled = vi.fn();
    render(wrap(<StaffClaimForm scope={scope} onFiled={onFiled} />));
    expect(await screen.findByText(/Available now: \$150\.00/)).toBeVisible();
    fireEvent.click(screen.getByRole("radio", { name: "A speaker or volunteer" }));
    const person = await screen.findByRole("combobox", { name: "Person" });
    await waitFor(() => expect(screen.getByRole("option", { name: "Asha (speaker)" })).toBeInTheDocument());
    expect(screen.queryByRole("option", { name: "Gone" })).toBeNull();
    fireEvent.change(person, { target: { value: "70" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Category" }), { target: { value: "rail" } });
    fireEvent.change(screen.getByLabelText("Amount (USD)"), { target: { value: "42.50" } });
    fireEvent.click(screen.getByRole("button", { name: "File claim" }));
    await waitFor(() => expect(onFiled).toHaveBeenCalled());
    const [path, options] = staffRequest.mock.calls.find(([, o]) => o?.method === "POST")!;
    expect(path).toBe("/admin/events/3/reimbursements/staff-claims/");
    const body = JSON.parse(options.body);
    expect(body).toMatchObject({ expected_version: 0, beneficiary_registration_id: 70, category: "rail", amount_minor: 4250, currency: "usd" });
    expect(options.headers["Idempotency-Key"]).toBe(body.operation_id);
  });

  it("claims for the signed-in staff member without a beneficiary", async () => {
    render(wrap(<StaffClaimForm scope={scope} onFiled={vi.fn()} />));
    fireEvent.change(await screen.findByRole("combobox", { name: "Category" }), { target: { value: "lodging" } });
    fireEvent.change(screen.getByLabelText("Amount (USD)"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: "File claim" }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([, o]) => o?.method === "POST")).toBe(true));
    const body = JSON.parse(staffRequest.mock.calls.find(([, o]) => o?.method === "POST")![1].body);
    expect(body).not.toHaveProperty("beneficiary_registration_id");
  });

  it("names the pool and registration refusals", () => {
    expect(staffClaimError(new StructuredApiError(409, { code: "budget_exhausted", detail: "x" }))).toMatch(/pool cannot cover/);
    expect(staffClaimError(new StructuredApiError(409, { code: "staff_claim_registration_required", detail: "x" }))).toMatch(/live registration/);
  });
});
