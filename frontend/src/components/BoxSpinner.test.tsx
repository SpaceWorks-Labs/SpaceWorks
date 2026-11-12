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
    expect(container.querySelectorAll("svg.lt .f:not(.z1)")).toHaveLength(4);
  });
  it("separates four mono flaps using the actual button ground, including cream text", () => {
    const { container } = render(<button style={{ backgroundColor: "rgb(0, 110, 99)", color: "rgb(255, 244, 232)" }}><BoxSpinner mono /></button>);
    const art = container.querySelector<HTMLElement>(".sw-box.mono")!;
    expect(art.style.getPropertyValue("--sw-ground")).toBe("rgb(0, 110, 99)");
    expect(document.querySelector("#sw-box-css")?.textContent).toContain(".sw-box.mono .dk{display:block!important}");
  });
  it("defaults the label to Loading, shares the one reduced-motion style, and backs Spinner", () => {
    render(<Spinner />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading");
    const styles = document.querySelectorAll("#sw-box-css");
    expect(styles).toHaveLength(1);
    expect(styles[0].textContent).toContain("prefers-reduced-motion:reduce");
  });
});
