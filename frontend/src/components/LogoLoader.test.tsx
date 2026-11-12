import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LogoLoader } from "./LogoLoader";

describe("LogoLoader", () => {
  it("is one polite status with a translated 'Loading' label and a decorative animated box", () => {
    const { container } = render(<LogoLoader />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    expect(container.querySelector(".sw-box.loop")).toHaveAttribute("aria-hidden", "true");
    // Both themes' artwork, four animated flaps each; CSS shows the one for html.dark.
    expect(container.querySelectorAll("svg.lt .f")).toHaveLength(4);
    expect(container.querySelectorAll("svg.dk .f")).toHaveLength(4);
  });
  it("announces a custom label, printed only when showLabel is set", () => {
    const { rerender } = render(<LogoLoader label="Opening makerspace..." />);
    expect(screen.getByText("Opening makerspace...")).toHaveClass("sr-only");
    rerender(<LogoLoader label="Opening makerspace..." showLabel />);
    expect(screen.getByText("Opening makerspace...")).not.toHaveClass("sr-only");
  });
  it("adds the animation CSS once, including the reduced-motion still", () => {
    render(<LogoLoader />);
    render(<LogoLoader size={96} />);
    const styles = document.querySelectorAll("#sw-box-css");
    expect(styles).toHaveLength(1);
    expect(styles[0].textContent).toContain("prefers-reduced-motion:reduce");
    expect(styles[0].textContent).toContain(".sw-box.loop");
  });
});
