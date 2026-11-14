import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { FeatureCoverage } from "./FeatureCoverage";

const areas = [
  "Inventory & loans", "Stocktake", "Machines & printing", "Events & hackathons", "Bookings",
  "Membership & ID cards", "Notifications", "Reports & analytics", "Money & receipts", "Mobile apps",
  "Connected devices", "Shop", "Donations & sponsors", "Presence & public TV",
  "Accounts, organizations & profiles", "Public pages", "Repairs & maintenance",
  "API access, backup & portability", "Security, privacy & help",
];

afterEach(() => {
  cleanup();
  document.documentElement.removeAttribute("data-theme");
});

describe.each(["light", "dark"])("landing feature coverage in %s mode", theme => {
  it("renders every area with its free or paid note and the optional rail", () => {
    document.documentElement.setAttribute("data-theme", theme);
    render(<FeatureCoverage />);
    const region = screen.getByRole("region", { name: "Every area can run free" });
    expect(within(region).getAllByRole("listitem")).toHaveLength(19);
    for (const area of areas) {
      const item = within(region).getByRole("heading", { level: 4, name: area }).closest("li")!;
      expect(within(item).getByText(/^Works free\./)).toBeVisible();
    }
    expect(within(region).getByText(/Turn off charges.enabled/)).toHaveTextContent(
      "Online payments are optional: Stripe or Razorpay can be added, and offline payments are recorded with a receipt.");
    for (const domain of ["loans", "machines", "events", "bookings", "membership", "shop", "donations"]) {
      expect(within(region).getAllByText(new RegExp(`charges\\.${domain}`)).length).toBeGreaterThan(0);
    }
    const shop = within(region).getByRole("heading", { level: 4, name: "Shop" }).closest("li")!;
    expect(within(shop).getByText("Works free. Catalogue and stock need no fee. Selling requires charges.shop; offline cash with a receipt works, online payments are optional.")).toBeVisible();
    expect(within(shop).queryByText(/given away/)).not.toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute("data-theme", theme);
    expect(region).not.toHaveAttribute("style");
    expect(region.className).not.toMatch(/border|bg-/);
  });
});
