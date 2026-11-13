import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { newSection, sectionLabels } from "./documentDefaults";
import { PublicPageSections } from "./PublicPageSections";
import type { PublicPageSection } from "./pageTypes";

const wall = (results: { id: number; name: string; tier: string; logo_url: string; website_url: string; blurb: string }[]) =>
  ({ id: "00000000-0000-0000-0000-000000000001", type: "sponsors", enabled: true,
    payload: { title: "Thank you", results } }) as PublicPageSection;

describe("sponsor wall section", () => {
  it("renders public sponsor cards with a safe outbound link", () => {
    render(<PublicPageSections image={() => null} sections={[wall([{ id: 1, name: "Acme Robotics", tier: "Gold",
      logo_url: "https://cdn.example/acme.png", website_url: "https://acme.example", blurb: "Motors for every bot" },
      { id: 2, name: "Plain Co", tier: "", logo_url: "", website_url: "javascript:alert(1)", blurb: "" }])]} />);
    const section = screen.getByRole("region", { name: "Thank you" });
    const link = within(section).getByRole("link", { name: "Acme Robotics" });
    expect(link).toHaveAttribute("rel", "noopener noreferrer nofollow");
    expect(within(section).getByRole("img", { name: "Acme Robotics logo" })).toBeInTheDocument();
    expect(within(section).queryByRole("link", { name: "Plain Co" })).not.toBeInTheDocument();
    expect(within(section).getByText("Plain Co")).toBeInTheDocument();
  });

  it("leaves an empty wall out and is offered in the editor", () => {
    render(<PublicPageSections image={() => null} sections={[wall([])]} />);
    expect(screen.queryByRole("heading", { name: "Thank you" })).not.toBeInTheDocument();
    expect(sectionLabels.sponsors).toBe("Sponsors");
    expect(newSection("sponsors").payload).toEqual({ title: "" });
  });
});
