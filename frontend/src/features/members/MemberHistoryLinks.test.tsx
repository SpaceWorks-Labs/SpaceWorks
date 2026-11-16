import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { MemberHistoryLinks } from "./MemberHistoryLinks";

describe("own history navigation", () => {
  it.each(["lab", ""])("keeps core money reachable with membership and rail off for slug %s", slug => {
    render(<MemberHistoryLinks slug={slug} modules={[]} features={[]} />);
    const nav = screen.getByRole("navigation", { name: "Your activity history" });
    expect(within(nav).getAllByRole("link")).toHaveLength(1);
    expect(within(nav).getByRole("link", { name: "Payments & receipts" })).toHaveAttribute("href", `${slug ? "/m/lab" : ""}/member/payments`);
    expect(screen.queryByRole("link", { name: "Borrowing history" })).toBeNull();
  });

  it("links every enabled owned history without requiring membership", async () => {
    const { container } = render(<MemberHistoryLinks slug="lab" modules={["request_workflow", "events", "bookings", "shop"]} features={["loans.enabled"]} />);
    for (const [name, path] of [["Borrowing history", "loans/history"], ["Event history", "events/history"],
      ["Booking history", "bookings?period=past"], ["Shop orders", "shop-orders"], ["Payments & receipts", "payments"]]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", `/m/lab/member/${path}`);
    }
    expect(container.textContent).not.toMatch(/token|shipping|sports/i);
    await expectNoA11yViolations(container);
  });

  it("omits borrowing when lending is off while keeping other enabled histories", () => {
    render(<MemberHistoryLinks slug="lab" modules={["request_workflow", "events"]} features={[]} />);
    expect(screen.queryByRole("link", { name: "Borrowing history" })).toBeNull();
    expect(screen.getByRole("link", { name: "Event history" })).toBeVisible();
    expect(screen.queryByRole("link", { name: "Shop orders" })).toBeNull();
  });
});
