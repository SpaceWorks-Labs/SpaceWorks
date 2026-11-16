import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type * as Api from "../../generated/api";
import { OrganizationPlans, type OrganizationMembershipFields } from "./OrganizationPlans";

vi.mock("../../lib/charges", () => ({ useChargesOn: () => true }));

const PLAN = {
  id: 1, name: "Maker monthly", description: "Open access to the workshop.", amount: "25.00", currency: "eur", joining_fee: "0.00",
  plan_type: "recurring", interval: "monthly", custom_days: null, fixed_end_date: null, join_mode: "open",
} as unknown as Api.PublicPlanCard;
const HOME = { name: "Harbour Lab", slug: "harbour", logo_url: null, canonical_url: "http://localhost:3000/m/harbour" } as Api.SpaceCard;

const show = (organization: OrganizationMembershipFields) =>
  render(<MemoryRouter><OrganizationPlans organization={organization} /></MemoryRouter>);

describe("OrganizationPlans", () => {
  it("is absent while the home space's plans are switched off (plans: null)", () => {
    const { container } = show({ name: "Harbour Makers", plans: null, home_space: HOME });
    expect(container).toBeEmptyDOMElement();
  });

  it("is absent before the read carries the new fields", () => {
    const { container } = show({ name: "Harbour Makers" });
    expect(container).toBeEmptyDOMElement();
  });

  it("lists the home space's plans, joins there and names the one shared member card", () => {
    show({ name: "Harbour Makers", home_space: HOME, plans: { title: "", count: 1, results: [PLAN], collection_url: "/api/v1/public/harbour/membership-plans" } });
    expect(screen.getByRole("heading", { name: "Membership" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Maker monthly" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Harbour Lab" })).toHaveAttribute("href", "/m/harbour");
    expect(screen.getByText(/Member cards are issued by Harbour Lab; one card covers the space and Harbour Makers/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Join" })).toHaveAttribute("href", "/m/harbour/member");
  });
});
