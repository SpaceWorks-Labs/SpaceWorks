import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Circle } from "lucide-react";
import { expect, it, vi } from "vitest";
import { BottomTabs } from "./BottomTabs";

it("keeps the visible 99+ badge and the exact count in the accessible name", () => {
  render(<MemoryRouter><BottomTabs label="Member sections" items={[{ key: "inbox", label: "Inbox", href: "/member/inbox", icon: Circle, badge: 102, badgeLabel: "unread" }]} activeKey="inbox" onMore={vi.fn()} /></MemoryRouter>);
  const link = screen.getByRole("link");
  expect(link).toHaveTextContent("99+");
  expect(link).toHaveAccessibleName(/^Inbox 99\+ \(102 unread\)$/);
});

const item = (key: string) => ({ key, label: key, href: `/m/${key}`, icon: Circle });
it("left/right/Home/End move focus between bottom tabs", () => {
  render(<MemoryRouter><BottomTabs label="Member sections" items={[item("a"), item("b"), item("c")]} activeKey="a" onMore={vi.fn()} /></MemoryRouter>);
  const [a, b, c] = screen.getAllByRole("link");
  a.focus(); fireEvent.keyDown(a, { key: "ArrowRight" }); expect(b).toHaveFocus();
  fireEvent.keyDown(b, { key: "End" }); expect(c).toHaveFocus();
  fireEvent.keyDown(c, { key: "ArrowRight" }); expect(a).toHaveFocus();
  fireEvent.keyDown(a, { key: "ArrowLeft" }); expect(c).toHaveFocus();
  fireEvent.keyDown(c, { key: "Home" }); expect(a).toHaveFocus();
});
