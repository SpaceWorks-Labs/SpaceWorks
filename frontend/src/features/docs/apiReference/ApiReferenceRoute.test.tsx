import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { fixtureSpec } from "./__tests__/apiFixture";
import { buildApiReference } from "./apiReferenceModel";
import { ApiReferenceRoute } from "./ApiReferenceRoute";
import { searchApiOperations } from "./apiSearch";

vi.mock("virtual:spaceworks-api-tags", async () => {
  const model = await import("./apiReferenceModel");
  const fixture = await import("./__tests__/apiFixture");
  const built = model.buildApiReference(fixture.fixtureSpec);
  return {
    tags: built.tags, version: built.version,
    loaders: Object.fromEntries(built.tags.map(tag => [tag.slug, () => Promise.resolve({ default: built.payloads[tag.slug] })])),
  };
});
vi.mock("virtual:spaceworks-api-index", async () => {
  const model = await import("./apiReferenceModel");
  const fixture = await import("./__tests__/apiFixture");
  const built = model.buildApiReference(fixture.fixtureSpec);
  return { default: built.index, tags: built.tags, version: built.version };
});

const renderAt = (tag?: string) => render(<MemoryRouter><ApiReferenceRoute tag={tag} /></MemoryRouter>);

describe("ApiReferenceRoute", () => {
  it("lists every section by group with counts", () => {
    renderAt();
    expect(screen.getByRole("heading", { level: 1, name: "API reference" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Inventory and loans" })).toBeInTheDocument();
    const loans = screen.getByRole("link", { name: /Loans.*Borrowing and returns.*2 endpoints/ });
    expect(loans).toHaveAttribute("href", "/docs/api/reference/loans");
    expect(screen.getByText(/version 9\.9\.9, 4 endpoints/)).toBeInTheDocument();
  });

  it("loads a section's chunk and renders its operations with an on-page list", async () => {
    renderAt("loans");
    expect(screen.getByRole("heading", { level: 1, name: "Loans" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading endpoints…");
    expect(await screen.findByRole("region", { name: "Create a loan" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "On this page" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /List public loans/ })).toHaveAttribute("href", "#public_loans_list");
  });

  it("says when a section does not exist", () => {
    renderAt("nope");
    expect(screen.getByRole("heading", { level: 1, name: "API section not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "All API sections" })).toHaveAttribute("href", "/docs/api/reference");
  });
});

describe("searchApiOperations", () => {
  it("matches summary, path and operation id, summary hits first", async () => {
    expect(await searchApiOperations("   ")).toEqual([]);
    const hits = await searchApiOperations("loans");
    expect(hits.map(hit => hit.id)).toEqual(["api:public_loans_list", "api:loans_create"]);
    expect(hits[1]).toEqual({ id: "api:loans_create", kind: "operation", title: "Create a loan",
      context: "POST /api/v1/admin/makerspaces/{makerspace_id}/loans/", href: "/docs/api/reference/loans#loans_create" });
    expect((await searchApiOperations("stock_clear")).map(hit => hit.href)).toEqual(["/docs/api/reference/stock#stock_clear"]);
    expect(await searchApiOperations("loans", 1)).toHaveLength(1);
    expect(buildApiReference(fixtureSpec).index).toHaveLength(4);
  });
});
