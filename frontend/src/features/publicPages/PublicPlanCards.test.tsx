import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type * as Api from "../../generated/api";
import { PublicPlanCards } from "./PublicPlanCards";

const charges = vi.hoisted(() => ({ on: true }));
vi.mock("../../lib/charges", () => ({ useChargesOn: () => charges.on }));

const plan = (overrides: Partial<Api.PublicPlanCard>) => ({
  id: 1, name: "Community", description: "", plan_type: "rolling", interval: "monthly", custom_days: null,
  fixed_end_date: null, amount: "10.00", currency: "usd", joining_fee: null, join_mode: "open", ...overrides,
}) as Api.PublicPlanCard;

function show(rows: Api.PublicPlanCard[]) {
  render(<MemoryRouter><PublicPlanCards rows={rows} slug="lab" /></MemoryRouter>);
}

describe("public plan cards", () => {
  it("shows a paid plan in its currency with its cadence and joining fee", () => {
    show([plan({ joining_fee: "5.00" })]);
    expect(screen.getByText("$10.00")).toBeVisible();
    expect(screen.getByText("per month")).toBeVisible();
    expect(screen.getByText("Joining fee $5.00")).toBeVisible();
  });

  it("calls a zero-priced plan Free and hides a zero joining fee", () => {
    show([plan({ amount: "0.00", joining_fee: "0.00" })]);
    expect(screen.getByText("Free")).toBeVisible();
    expect(screen.queryByText("per month")).toBeNull();
    expect(screen.queryByText(/Joining fee/)).toBeNull();
  });

  it("shows no price at all while membership charges are off (#184)", () => {
    charges.on = false;
    show([plan({ joining_fee: "5.00" })]);
    expect(screen.queryByText("$10.00")).toBeNull();
    expect(screen.queryByText(/Joining fee/)).toBeNull();
    charges.on = true;
  });
});
