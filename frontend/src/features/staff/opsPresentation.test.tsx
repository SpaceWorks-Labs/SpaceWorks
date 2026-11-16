import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { ListLayout } from "../../components/layouts";
import { useOpsTabs } from "./opsPresentation";

function Harness() {
  const tabs = useOpsTabs("cardsTab", [{ key: "cards", label: "Cards" }, { key: "issue", label: "Issue" }], "cards");
  const location = useLocation();
  const navigate = useNavigate();
  return <div onClickCapture={tabs.onClickCapture}>
    <ListLayout header={{ title: "Member cards" }} tabs={tabs.tabs} activeTab={tabs.active} state={{ status: "ready" }}
      empty={{ message: "No cards yet." }} body={{ kind: "rows", rows: <output>{location.search}</output> }} />
    <button onClick={() => navigate(-1)}>Back</button>
  </div>;
}
describe("ops URL tabs", () => {
  it("preserves deep links and filters, supports back, and renders one heading", () => {
    render(<MemoryRouter initialEntries={["/admin/cards?cardsTab=cards&event=9&page=3"]}><Harness /></MemoryRouter>);
    fireEvent.click(screen.getByRole("link", { name: "Issue" }));
    expect(screen.getByRole("link", { name: "Issue" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("status")).toHaveTextContent("cardsTab=issue&event=9&page=3");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("link", { name: "Cards" })).toHaveAttribute("aria-current", "page");
  });
});
