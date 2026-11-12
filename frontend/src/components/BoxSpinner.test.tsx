import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BoxSpinner } from "./BoxSpinner";
import { Spinner } from "./ui/Spinner";

describe("BoxSpinner", () => {
  it("is a polite status with a sr-only label and decorative, unfocusable artwork", () => {
    const { container } = render(<BoxSpinner label="Loading fonts…" size={16} />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading fonts…");
    expect(screen.getByText("Loading fonts…")).toHaveClass("sr-only");
    const art = container.querySelector(".sw-box.loop");
    expect(art).toHaveAttribute("aria-hidden", "true");
    expect(art).toHaveStyle({ height: "16px" });
    expect(container.querySelector("[tabindex],a,button")).toBeNull();
    expect(container.querySelectorAll("svg.lt .f")).toHaveLength(4);
  });
  it("defaults the label to Loading, shares the one reduced-motion style, and backs Spinner", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    const styles = document.querySelectorAll("#sw-box-css");
    expect(styles).toHaveLength(1);
    expect(styles[0].textContent).toContain("prefers-reduced-motion:reduce");
  });
});
