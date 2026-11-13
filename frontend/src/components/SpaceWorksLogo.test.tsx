/// <reference types="node" />
import { readFileSync } from "node:fs";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SpaceWorksLogo, { SpaceWorksBadge, type SpaceWorksLogoProps } from "./SpaceWorksLogo";
import { logoMasters } from "./spaceWorksLogoPaths";

const source = (name: string) => new DOMParser().parseFromString(readFileSync(
  `../docs/brand/${name}.svg`, "utf8",
), "image/svg+xml").documentElement;

afterEach(() => {
  cleanup();
  document.documentElement.classList.remove("dark");
});

describe("Space Works logo masters", () => {
  const cases = [
    [{ variant: "symbol", ground: "light" }, "symbol"],
    [{ variant: "symbol", ground: "dark" }, "symbol-reversed"],
    [{ variant: "stacked", ground: "light" }, "lockup-stacked"],
    [{ variant: "stacked", ground: "dark" }, "lockup-stacked-reversed"],
    [{ variant: "horizontal", ground: "light" }, "lockup-horizontal"],
    [{ variant: "horizontal", ground: "dark" }, "lockup-horizontal-reversed"],
    [{ variant: "symbol", ground: "light", oneColour: true }, "symbol-one-colour-ink"],
    [{ variant: "stacked", ground: "light", oneColour: true }, "lockup-stacked-one-colour-ink"],
    [{ variant: "horizontal", ground: "light", oneColour: true }, "lockup-horizontal-one-colour-ink"],
    [{ variant: "symbol", ground: "dark", oneColour: true }, "symbol-reversed"],
  ] satisfies [SpaceWorksLogoProps, string][];

  it.each(cases)("uses the exact master for %j", (props, name) => {
    render(<SpaceWorksLogo {...props} />);
    const logo = screen.getByRole("img", { name: "Space Works" });
    const master = source(name);
    expect(logo.getAttribute("viewBox")).toBe(master.getAttribute("viewBox"));
    expect([...logo.querySelectorAll("path")].map(path => [path.getAttribute("fill"), path.getAttribute("d")]))
      .toEqual([...master.querySelectorAll("path")].map(path => [path.getAttribute("fill"), path.getAttribute("d")]));
    const width = Number(logo.getAttribute("width"));
    const height = Number(logo.getAttribute("height"));
    expect(height).toBeGreaterThanOrEqual(48);
    if (props.variant !== "symbol") expect(width).toBeGreaterThanOrEqual(180);
    expect((logo.parentElement as HTMLElement).style.padding).toBe(`${height / 4}px`);
  });

  it("clamps untyped and legacy callers, including non-finite sizes", () => {
    const { rerender } = render(<SpaceWorksLogo size={22} withWordmark />);
    expect(screen.getByRole("img").getAttribute("height")).toBe("48");
    for (const size of [-10, 22, NaN, Infinity]) {
      rerender(<SpaceWorksLogo {...({ variant: "horizontal", size } as SpaceWorksLogoProps)} />);
      expect(Number(screen.getByRole("img").getAttribute("height"))).toBeGreaterThanOrEqual(48);
      expect(Number(screen.getByRole("img").getAttribute("width"))).toBeGreaterThanOrEqual(180);
    }
  });

  it("follows the app theme for legacy callers and honours explicit grounds", async () => {
    const { rerender } = render(<SpaceWorksLogo />);
    await act(async () => { document.documentElement.classList.add("dark"); });
    expect(screen.getByRole("img").parentElement?.getAttribute("data-logo")).toBe("symbol-reversed");
    rerender(<SpaceWorksLogo ground="light" />);
    expect(screen.getByRole("img").parentElement?.getAttribute("data-logo")).toBe("symbol");
  });

  it("clips the horizontal lockup's symbol exactly as the master does", () => {
    const { container } = render(<SpaceWorksLogo variant="horizontal" ground="light" />);
    const rect = container.querySelector("clipPath rect");
    expect([rect?.getAttribute("width"), rect?.getAttribute("height")]).toEqual(["61.8462", "57.6"]);
    // The four flaps sit outside the clip so delight's logo unfold can move them; the rest stay clipped.
    expect(container.querySelectorAll("g[clip-path] path")).toHaveLength(3);
    expect(container.querySelectorAll("g[clip-path] ~ path.sw-logo-flap")).toHaveLength(4);
  });

  it("gives separate instances unique titles and hides decorative artwork", () => {
    const { container } = render(<><SpaceWorksLogo /><SpaceWorksLogo /><SpaceWorksLogo decorative /></>);
    expect(screen.getAllByRole("img", { name: "Space Works" })).toHaveLength(2);
    const titles = [...container.querySelectorAll("title")];
    expect(titles).toHaveLength(2);
    expect(titles[0].id).not.toBe(titles[1].id);
    expect(container.querySelector('svg[aria-hidden="true"] title')).toBeNull();
  });

  it("keeps the badge link named and the small badge at symbol minimum", () => {
    const { container } = render(<MemoryRouter><SpaceWorksBadge /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Space Works — Open makerspace listing" }).getAttribute("href")).toBe("/");
    expect(container.querySelector("svg")?.getAttribute("height")).toBe("48");
  });

  it("includes exactly the nine approved masters", () => {
    expect(Object.keys(logoMasters)).toEqual([
      "symbol", "symbol-reversed", "symbol-one-colour-ink",
      "lockup-stacked", "lockup-stacked-reversed", "lockup-stacked-one-colour-ink",
      "lockup-horizontal", "lockup-horizontal-reversed", "lockup-horizontal-one-colour-ink",
    ]);
  });
});
