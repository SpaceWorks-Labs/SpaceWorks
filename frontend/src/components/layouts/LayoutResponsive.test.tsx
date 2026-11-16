import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../test/axe";
import { Field } from "../ui";
import { DashboardLayout, FormPageLayout, ListLayout, PublicDetailLayout, PublicLayout } from "./index";

afterEach(() => vi.unstubAllGlobals());
function viewport(width: number) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: width >= Number(query.match(/min-width: (\d+)px/)?.[1] ?? Infinity),
    addEventListener: vi.fn(), removeEventListener: vi.fn() }));
}
it.each([375, 768, 1280])("keeps exactly one public action form at %ipx", async width => {
  viewport(width);
  const { container } = render(<PublicLayout state={{ status: "ready" }} makerspace={{ name: "Lab", slug: "lab" }} nav={[]} footer={{ links: [] }}>
    <PublicDetailLayout state={{ status: "ready" }} title="Workshop" sections={[{ id: "about", label: "About", content: <p>Workshop details</p> }]}
      actionCard={{ title: "Join", state: "open", form: <Field label="Your name"><input id="registration-name" className="desk-input" /></Field>,
        primary: { label: "Register" }, mobileBar: { summary: "Free", label: "Open registration" } }} />
  </PublicLayout>);
  if (width < 768) {
    expect(screen.queryByRole("textbox", { name: "Your name" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open registration" }));
    expect(screen.getByRole("dialog", { name: "Join" })).toBeInTheDocument();
  } else expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getAllByRole("textbox", { name: "Your name" })).toHaveLength(1);
  expect(document.querySelectorAll("#registration-name")).toHaveLength(1);
  expect(container.querySelectorAll("#main-content")).toHaveLength(1);
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  await expectNoA11yViolations(container);
});
it.each([375, 768, 1280])("mounts one preview and discloses filters at %ipx", width => {
  viewport(width);
  const view = render(<FormPageLayout state={{ status: "ready" }} header={{ title: "Create" }} form={<p>Form fields</p>}
    submit={{ label: "Create" }} preview={{ label: "Preview", content: <p>Preview content</p> }} />);
  if (width < 768) {
    expect(screen.queryByText("Preview content")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
  }
  expect(screen.getAllByText("Preview content")).toHaveLength(1);
  view.unmount();
  render(<ListLayout state={{ status: "ready" }} header={{ title: "Tools" }} empty={{ message: "No tools" }} body={{ kind: "rows", rows: <p>Drill</p> }}
    filters={{ controls: <Field label="Sort"><select className="desk-input"><option>Name</option></select></Field> }} />);
  // Filter controls live behind the Filters disclosure at every width; it mounts them exactly once.
  expect(screen.queryByRole("combobox", { name: "Sort" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
  expect(screen.getAllByRole("combobox", { name: "Sort" })).toHaveLength(1);
});
it.each([375, 768, 1280])("limits the small-screen rail to three mounted activities at %ipx", width => {
  viewport(width);
  render(<DashboardLayout state={{ status: "ready" }} header={{ eyebrow: "Good morning", title: "Home" }} stats={[]} main={[]}
    rail={{ title: "Activity", items: [1, 2, 3, 4].map(n => ({ key: String(n), actor: "Meera", children: `Activity ${n}`, date: "2026-10-15T10:00:00Z" })) }} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(width < 1280 ? 3 : 4);
});
