import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";
import { LayoutFrame } from "./LayoutFrame";
import { ListLayout } from "./ListLayout";
import { DetailLayout } from "./DetailLayout";
import { AppShell } from "../shell/AppShell";
import type { AppShellProps } from "../shell/types";

const ready = { status: "ready" } as const;
const tabs = [{ key: "a", label: "Overview" }, { key: "b", label: "History" }];

it("only standalone outer frames own a landmark and skip target, including loading shells", () => {
  const { container, rerender } = render(<LayoutFrame standalone><LayoutFrame standalone>Nested</LayoutFrame></LayoutFrame>);
  expect(container.querySelectorAll("#main-content")).toHaveLength(1);
  expect(screen.getAllByRole("main")).toHaveLength(1);
  rerender(<LayoutFrame>Embedded</LayoutFrame>);
  expect(container.querySelector("#main-content")).not.toBeInTheDocument();
  expect(screen.queryByRole("main")).not.toBeInTheDocument();
});

it("does not duplicate the AppShell target even for a standalone child", () => {
  const props: Omit<AppShellProps, "children"> = { variant: "staff", nav: [], activeKey: "home", compactNav: "bottom-tabs",
    workspace: { name: "Workshop", subtitle: "Community", avatar: { kind: "icon", icon: "Building2", tone: "accent" } },
    user: { name: "Meera", menu: [], onSignOut: vi.fn() } };
  const { container } = render(<MemoryRouter><AppShell {...props}><LayoutFrame standalone>Page</LayoutFrame></AppShell></MemoryRouter>);
  expect(container.querySelectorAll("#main-content")).toHaveLength(1);
  expect(screen.getAllByRole("main")).toHaveLength(1);
  expect(container.querySelector("#main-content")).toHaveAttribute("tabindex", "-1");
});

it("passes sticky and bulk primary actions through ListLayout", () => {
  const primary = vi.fn(), bulk = vi.fn();
  render(<ListLayout state={ready} header={{ title: "Tools", primary: { label: "Add tool", onClick: primary } }}
    stickyPrimaryOnMobile body={{ kind: "rows", rows: "Rows" }} empty={{ message: "No tools" }}
    bulkBar={{ count: 2, primary: { label: "Move selected", onClick: bulk }, actions: [], onClear: vi.fn() }} />);
  expect(screen.getByRole("button", { name: "Add tool" }).parentElement).toHaveClass("sw-sticky-primary");
  const action = screen.getByRole("button", { name: "Move selected" });
  expect(action).toHaveClass("desk-button-primary"); fireEvent.click(action);
  expect(bulk).toHaveBeenCalledOnce();
});

function Controlled({ detail = false }: { detail?: boolean }) {
  const [active, change] = useState("a");
  return detail ? <DetailLayout state={ready} title="Item" tabs={tabs} activeTab={active} onTabChange={change} main={<p>{active} content</p>} />
    : <ListLayout state={ready} header={{ title: "Items" }} tabs={tabs} activeTab={active} onTabChange={change}
      body={{ kind: "rows", rows: <p>{active} content</p> }} empty={{ message: "No items" }} />;
}
for (const detail of [false, true]) it(`connects ${detail ? "detail" : "list"} controlled tabs to layout content`, () => {
  render(<Controlled detail={detail} />);
  expect(screen.getByRole("tabpanel", { name: "Overview" })).toHaveTextContent("a content");
  const first = screen.getByRole("tab", { name: "Overview" }); first.focus();
  fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(screen.getByRole("tab", { name: "History" })).toHaveFocus();
  expect(screen.getByRole("tabpanel", { name: "History" })).toHaveTextContent("b content");
  expect(screen.queryByText("a content")).not.toBeInTheDocument();
});

it("retains child component state while a controlled filter tab changes", () => {
  function Child() {
    const [draft, setDraft] = useState("");
    return <input aria-label="Draft" value={draft} onChange={event => setDraft(event.target.value)} />;
  }
  function Stable() {
    const [active, change] = useState("a");
    return <ListLayout state={ready} header={{ title: "Items" }} tabs={tabs} activeTab={active} onTabChange={change}
      body={{ kind: "rows", rows: <Child /> }} empty={{ message: "No items" }} />;
  }
  render(<Stable />);
  const input = screen.getByRole("textbox", { name: "Draft" });
  fireEvent.change(input, { target: { value: "Unsent draft" } });
  fireEvent.click(screen.getByRole("tab", { name: "History" }));
  expect(screen.getByRole("tabpanel", { name: "History" })).toContainElement(input);
  expect(input).toHaveValue("Unsent draft");
});
