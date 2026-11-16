import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { expectNoA11yViolations } from "../../../test/axe";
import type { Makerspace } from "../../../types/inventory";
import { SpacesSection } from "./SpacesSection";

type QueryState = { data?: Makerspace[]; isLoading?: boolean; isError?: boolean; isFetching?: boolean; refetch: () => void };
const query = vi.hoisted(() => ({ value: {} as QueryState }));
vi.mock("../../inventory/usePublicInventory", () => ({ usePublicMakerspaces: () => query.value }));
vi.mock("../../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false }) }));

const many = (n: number): Makerspace[] => Array.from({ length: n }, (_, i) => ({
  name: `Space ${i + 1}`, public_code: `C${i}`, slug: `space-${i + 1}`, location: "Town",
}));
function renderSection(state: Partial<QueryState>, props: Parameters<typeof SpacesSection>[0] = {}) {
  query.value = { refetch: vi.fn(), ...state };
  return render(<MemoryRouter><SpacesSection {...props} /></MemoryRouter>);
}
const cardLinks = () => screen.getAllByRole("link").filter(link => link.getAttribute("href")?.startsWith("/m/"));

describe("SpacesSection", () => {
  it("shows the first spaces under an h2 and links to the full directory", () => {
    renderSection({ data: many(9) });
    expect(screen.getByRole("heading", { level: 2, name: "Find a makerspace near you" })).toHaveAttribute("id", "spaces");
    expect(cardLinks()).toHaveLength(6);
    expect(screen.getByRole("link", { name: "See all 9 makerspaces" })).toHaveAttribute("href", "/spaces");
  });

  it("takes a limit, heading, id and link target, and hides the link when everything fits", () => {
    const { unmount } = renderSection({ data: many(5) }, { limit: 3, heading: "Spaces", id: "home-spaces", seeAllHref: "/discover/spaces" });
    expect(screen.getByRole("heading", { level: 2, name: "Spaces" })).toHaveAttribute("id", "home-spaces");
    expect(cardLinks()).toHaveLength(3);
    expect(screen.getByRole("link", { name: "See all 5 makerspaces" })).toHaveAttribute("href", "/discover/spaces");
    unmount();
    renderSection({ data: many(2) });
    expect(screen.queryByRole("link", { name: /See all/ })).toBeNull();
  });

  it("renders the loading, empty and error states in place of the cards", () => {
    const { unmount } = renderSection({ isLoading: true });
    expect(screen.getByRole("status", { name: "Loading spaces" })).toBeInTheDocument();
    unmount();
    const second = renderSection({ data: [] });
    expect(screen.getByRole("heading", { name: "No public spaces yet" })).toBeInTheDocument();
    second.unmount();
    const refetch = vi.fn();
    renderSection({ isError: true, refetch });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("has no axe violations", async () => {
    const { container } = renderSection({ data: many(4) });
    await expectNoA11yViolations(container);
  });
});
