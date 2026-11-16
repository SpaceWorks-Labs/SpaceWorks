import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, it } from "vitest";
import { LayoutGallery } from "./LayoutGallery";
import { layoutGalleryExamples } from "./LayoutGalleryExamples";
import { ListLayout } from "./ListLayout";
import { ContentTarget } from "./LayoutFrame";
import { expectNoA11yViolations } from "../../test/axe";

it("offers every route-free sample and keeps just one selected layout mounted", async () => {
  function GalleryInPage() {
    const [overlay, setOverlay] = useState(false);
    return <div onChange={event => {
      if (event.target instanceof HTMLSelectElement) setOverlay(["Detail drawer", "Flow dialog"].includes(event.target.value));
    }}>
      {overlay ? <main id="main-content" tabIndex={-1}><h1>Workspace</h1></main> : null}
      <ContentTarget.Provider value={overlay}><LayoutGallery /></ContentTarget.Provider>
    </div>;
  }
  render(<GalleryInPage />);
  for (const example of layoutGalleryExamples) {
    fireEvent.change(screen.getByRole("combobox", { name: "Layout gallery" }), { target: { value: example } });
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.querySelectorAll("#main-content")).toHaveLength(1);
  }
});
it("lets a shell supply main while keeping its skip target in all query states", async () => {
  const { container } = render(<main id="main-content" tabIndex={-1} aria-label="Shell"><ContentTarget.Provider value={true}><ListLayout state={{ status: "loading" }} header={{ title: "Tools" }}
    body={{ kind: "rows", rows: null }} empty={{ message: "No tools" }} /></ContentTarget.Provider></main>);
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
  await expectNoA11yViolations(container);
});
