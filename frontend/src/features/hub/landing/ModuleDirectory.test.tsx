import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { moduleKeys, moduleLabel } from "../../../lib/moduleLabels";
import { featureCatalogue } from "../featuresPage/catalogue";
import { moduleMoney, moduleWithout } from "../featuresPage/moduleLifecycle";
import { moduleSlug } from "../featuresPage/moduleGroups";
import { ModuleDirectory } from "./ModuleDirectory";

describe("landing module catalogue (decision 601)", () => {
  it("lists every live module once with its shared description, off-state, money and feature link", () => {
    const { container } = render(<MemoryRouter><ModuleDirectory /></MemoryRouter>);
    const items = [...container.querySelectorAll<HTMLElement>("[data-landing-module]")];
    expect(items.map(item => item.dataset.landingModule).sort()).toEqual(moduleKeys().sort());
    expect(Object.keys(moduleWithout()).sort()).toEqual(moduleKeys().sort());
    const catalogue = featureCatalogue();
    for (const key of moduleKeys()) {
      const item = items.find(row => row.dataset.landingModule === key)!;
      expect(within(item).getByRole("link", { name: moduleLabel(key) })).toHaveAttribute("href", `/features/${moduleSlug(key)}`);
      expect(item).toHaveTextContent(catalogue[key].what);
      expect(item).toHaveTextContent(moduleWithout()[key]);
      expect(item).toHaveTextContent(moduleMoney(key));
    }
    expect(screen.getByRole("link", { name: "Explore every module and feature switch" })).toHaveAttribute("href", "/features");
  });
});
