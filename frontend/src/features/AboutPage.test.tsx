import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { expectNoA11yViolations } from "../test/axe";
import { AboutPage } from "./AboutPage";

describe("AboutPage", () => {
  it("opens with the Citron field and keeps every link", async () => {
    const { container } = render(<MemoryRouter><AboutPage /></MemoryRouter>);
    const title = screen.getByRole("heading", { level: 1, name: "Open-source makerspace management" });
    expect(title.closest("section")).toHaveClass("sw-field-citron");
    expect(container.querySelectorAll(".font-accent, .sw-hero-title")).toHaveLength(0);
    expect(screen.getAllByRole("link", { name: /Browse spaces/ }).length).toBeGreaterThanOrEqual(2);
    for (const link of screen.getAllByRole("link", { name: /Browse spaces/ })) expect(link).toHaveAttribute("href", "/spaces");
    expect(screen.getAllByRole("link", { name: /Staff sign-in/ }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("link", { name: /GNU Affero General Public License/ })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /License/ }).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/member");
    await expectNoA11yViolations(container);
  });
});
