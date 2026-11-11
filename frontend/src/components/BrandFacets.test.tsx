import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BrandFacets } from "./BrandFacets";
import { logoMasters } from "./spaceWorksLogoPaths";

describe("BrandFacets", () => {
  it("draws the symbol master's top diamond and right face verbatim, decoratively", () => {
    const { container } = render(<BrandFacets size="lg" />);
    const svg = container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(svg).toHaveAttribute("width", "360");
    const paths = [...svg.querySelectorAll("path")];
    expect(paths.map(path => path.getAttribute("d"))).toEqual([logoMasters.symbol.paths[2].d, logoMasters.symbol.paths[1].d]);
    expect(paths.map(path => path.getAttribute("fill"))).toEqual(["rgb(var(--color-emphasis))", "rgb(var(--color-warn))"]);
  });

  it.each(["teal", "orange"] as const)("renders the %s diamond alone", (tone) => {
    const { container } = render(<BrandFacets size="sm" tone={tone} />);
    expect(container.querySelectorAll("path")).toHaveLength(1);
  });

  it("never renders the assembled logo or transforms the artwork", () => {
    const { container } = render(<><BrandFacets /><BrandFacets tone="teal" /></>);
    for (const svg of container.querySelectorAll("svg")) {
      expect(svg.querySelectorAll("path").length).toBeLessThanOrEqual(2);
      expect(svg.innerHTML).not.toMatch(/transform|rotate/);
      expect(svg).not.toHaveAttribute("role");
    }
  });
});
