import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { DocsPage } from "./DocsPage";
import { allDocs, neighbours } from "./docsIndex";
vi.mock("../organizations/publicDirectoryApi", () => ({ useOrganizationDirectoryEnabled: () => false }));
vi.mock("../hosting/hostingApi", () => ({ useHostingConfig: () => ({ data: false }) }));
vi.mock("../hub/useLandingEnabled", () => ({ useLandingEnabled: () => ({ loading: false, enabled: true }) }));
vi.mock("../hub/HubAccount", () => ({ HubAccount: () => <a href="/member">Sign in</a> }));

// The API reference has its own tests; here its search is a stub so the palette stays fast.
vi.mock("./apiReference/apiSearch", () => ({
  searchApiOperations: vi.fn(async (query: string) => query.includes("loan")
    ? [{ id: "op", kind: "operation", title: "List loans", context: "GET /api/v1/admin/loans/", href: "/docs/api/reference/admin-loans#list" }] : []),
}));

beforeAll(() => {
  // jsdom has neither of these; the TOC and article scroll call them.
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
  Element.prototype.scrollIntoView = vi.fn();
});

function Where() { const location = useLocation(); return <p data-testid="where">{location.pathname}{location.hash}</p>; }
function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/docs/*" element={<><DocsPage /><Where /></>} /></Routes></MemoryRouter>);
}

const install = allDocs.find(entry => entry.id === "install-and-update")!;
const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

describe("DocsPage", () => {
  it("opens on the docs home with every group and the API reference", () => {
    renderAt("/docs");
    expect(screen.getByRole("heading", { level: 1, name: "Space Works documentation" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Hosting" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /API reference/ })[0]).toHaveAttribute("href", "/docs/api/reference");
    const nav = screen.getByRole("navigation", { name: "Documentation" });
    expect(within(nav).getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  it("renders an article from its slug with breadcrumbs, edit link, TOC and previous/next", async () => {
    expect(install).toBeDefined();
    renderAt("/docs/install-and-update");
    expect(screen.getByRole("heading", { level: 1, name: install.title })).toBeInTheDocument();
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getByRole("link", { name: "Docs" })).toHaveAttribute("href", "/docs");
    expect(screen.getByRole("link", { name: /Edit this page on GitHub/ }))
      .toHaveAttribute("href", "https://github.com/SpaceWorks-Labs/SpaceWorks/edit/main/docs/install-and-update.md");
    // A heading's accessible name also carries its "Link to this section" anchor.
    const first = install.headings[0];
    expect(await screen.findByRole("heading", { level: 2, name: new RegExp(`^${escape(first.text)}`) }, { timeout: 15000 })).toHaveAttribute("id", first.id);
    const toc = screen.getByRole("navigation", { name: "On this page" });
    expect(within(toc).getAllByRole("link")[0]).toHaveAttribute("href", `#${first.id}`);
    const pager = screen.getByRole("navigation", { name: "Previous and next pages" });
    const { previous, next } = neighbours("install-and-update");
    if (previous) expect(within(pager).getByRole("link", { name: new RegExp(escape(previous.title)) })).toHaveAttribute("href", `/docs/${previous.id}`);
    if (next) expect(within(pager).getByRole("link", { name: new RegExp(escape(next.title)) })).toHaveAttribute("href", `/docs/${next.id}`);
    const current = within(screen.getByRole("navigation", { name: "Documentation" })).getByRole("link", { name: install.title });
    expect(current).toHaveAttribute("aria-current", "page");
  }, 20000);

  it("shows a not-found page for an unknown slug", () => {
    renderAt("/docs/no/such/page");
    expect(screen.getByRole("heading", { level: 1, name: "This page isn’t in the docs" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to the documentation home" })).toHaveAttribute("href", "/docs");
  });

  it("opens the search palette with Ctrl+K and navigates results with the keyboard", async () => {
    renderAt("/docs");
    act(() => { fireEvent.keyDown(window, { key: "k", ctrlKey: true }); });
    const dialog = screen.getByRole("dialog", { name: "Search the documentation" });
    const input = within(dialog).getByRole("combobox");
    expect(input).toHaveFocus();
    fireEvent.change(input, { target: { value: "install" } });
    const options = within(dialog).getAllByRole("option");
    expect(options.length).toBeGreaterThan(1);
    expect(options[0]).toHaveAttribute("aria-selected", "true");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(within(dialog).getAllByRole("option")[1]).toHaveAttribute("aria-selected", "true");
    expect(input).toHaveAttribute("aria-activedescendant", within(dialog).getAllByRole("option")[1].id);
    fireEvent.keyDown(input, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("finds API operations and opens the chosen result", async () => {
    renderAt("/docs?q=loan");
    const dialog = screen.getByRole("dialog", { name: "Search the documentation" });
    const operation = await within(dialog).findByRole("option", { name: /List loans/ }, { timeout: 10000 });
    fireEvent.click(operation);
    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent("/docs/api/reference/admin-loans#list"));
  }, 20000);
});
