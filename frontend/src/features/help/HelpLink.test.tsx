import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { HelpLink, StaffScreenHelp } from "./HelpLink";

const on = { slug: "tinkerspace", enabled_features: ["platform.help_centre"] };
const off = { slug: "tinkerspace", enabled_features: ["ui.delight"] };

describe("Help links beside staff screens", () => {
  it("deep-links the screen's article in a new tab", async () => {
    const { container } = render(<StaffScreenHelp tab="requests" makerspace={on} />);
    const link = screen.getByRole("link", { name: /Help for this page/ });
    expect(link).toHaveAttribute("href", "/m/tinkerspace/help/inventory-manager/requests-queue");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    await expectNoA11yViolations(container);
  });

  it("hides every Help link when the space switches the help centre off", () => {
    const { container } = render(<><StaffScreenHelp tab="requests" makerspace={off} /><HelpLink article="member/borrow-tools" makerspace={off} /></>);
    expect(screen.queryByRole("link")).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("uses /help on a single-space origin and keeps the superadmin's platform session", () => {
    render(<StaffScreenHelp tab="migration" makerspace={on} singleTenant platform />);
    expect(screen.getByRole("link", { name: /Help/ })).toHaveAttribute("href", "/help/superadmin/tenant-migration?context=platform");
  });

  it("shows the platform guide when no space is chosen, and nothing for an unmapped screen", () => {
    const { rerender } = render(<StaffScreenHelp tab="platform-dashboard" platform />);
    expect(screen.getByRole("link", { name: /Help/ })).toHaveAttribute("href", "/help/superadmin/platform-dashboard?context=platform");
    rerender(<StaffScreenHelp tab="not-a-tab" makerspace={on} />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
