import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { anonymous, staff } = vi.hoisted(() => ({ anonymous: vi.fn(), staff: vi.fn() }));
vi.mock("../../lib/api/requests", async (original) => ({ ...await original<object>(), publicAnonymousRequest: anonymous }));
vi.mock("../../lib/api", async (original) => ({ ...await original<object>(), staffRequest: staff }));
vi.mock("../inventory/usePublicInventory", () => ({ useTenantBootstrap: () => ({ data: undefined }) }));
vi.mock("../../lib/tenant", async (original) => {
  const actual = await original<typeof import("../../lib/tenant")>();
  return { ...actual, useTenant: () => ({ mode: "central" }), useTenantPath: (slug: string) => (sub = "") => actual.tenantPath("central", slug, sub) };
});

import { LegalPage } from "./LegalPage";
import { LegalPagesEditor } from "./LegalPagesEditor";
import { splitTitle } from "./LegalMarkdown";

const page = (markdown: string, source = "default") => ({ slug: "privacy", markdown, source, language: "en", updated_at: "2026-11-01T10:00:00Z" });

function mount(path: string, element: import("react").ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes><Route path="/privacy" element={element} /><Route path="/m/:slug/privacy" element={element} /><Route path="/admin" element={element} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => { anonymous.mockReset(); staff.mockReset(); });

describe("legal pages (parity A13)", () => {
  it("renders the Markdown with its own title and never raw HTML", async () => {
    anonymous.mockResolvedValue(page("# Privacy\n\n## What we keep\n\nYour **name**.<script>window.pwned = 1</script><img src=x onerror=alert(1)>\n\n[Terms](/terms) · [Site](https://example.org)"));
    const { container } = mount("/privacy", <LegalPage slug="privacy" />);
    expect(await screen.findByRole("heading", { level: 1, name: "Privacy" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "What we keep" })).toBeVisible();
    expect(screen.getByText("name").tagName).toBe("STRONG");
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img[src='x']")).toBeNull();
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: /Site/ })).toHaveAttribute("target", "_blank");
    expect(anonymous).toHaveBeenCalledWith("/discover/legal/privacy/");
  });

  it("asks for the space's own text on a space's page", async () => {
    anonymous.mockResolvedValue(page("Our own rules.", "space"));
    mount("/m/north-lab/privacy", <LegalPage slug="privacy" />);
    expect(await screen.findByText("Our own rules.")).toBeVisible();
    expect(anonymous).toHaveBeenCalledWith("/discover/legal/privacy/?space=north-lab");
  });

  it("offers a retry when the page cannot load", async () => {
    anonymous.mockRejectedValue(new Error("down"));
    mount("/privacy", <LegalPage slug="privacy" />);
    expect(await screen.findByText("This page could not be loaded. Try again.")).toBeVisible();
  });

  it("splits only a leading level-one heading", () => {
    expect(splitTitle("# Terms\nBody")).toEqual({ title: "Terms", body: "Body" });
    expect(splitTitle("## Not a title\nBody")).toEqual({ title: null, body: "## Not a title\nBody" });
  });

  it("lets a space save its own text and clear it back to the platform's", async () => {
    staff.mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "PUT"
      ? page(JSON.parse(String(options.body)).markdown || "Platform text", JSON.parse(String(options.body)).markdown ? "space" : "platform")
      : page("Platform text", "platform"));
    mount("/admin", <LegalPagesEditor scope={{ kind: "space", makerspaceId: 4 }} />);
    const box = await screen.findByRole("textbox");
    expect(box).toHaveValue("");
    await waitFor(() => expect(box).toHaveAttribute("placeholder", "Platform text"));
    fireEvent.change(box, { target: { value: "# Ours" } });
    fireEvent.click(screen.getByRole("button", { name: "Save page" }));
    await waitFor(() => expect(staff).toHaveBeenCalledWith("/admin/makerspace/4/legal-pages/privacy", { method: "PUT", body: JSON.stringify({ markdown: "# Ours" }) }));
  });

  it("lets the operator return a page to the shipped default", async () => {
    staff.mockImplementation(async (_path: string, options?: RequestInit) => options?.method === "DELETE" ? undefined : page("Operator text", "platform"));
    mount("/admin", <LegalPagesEditor scope={{ kind: "platform" }} />);
    fireEvent.click(await screen.findByRole("button", { name: "Return to the shipped default" }));
    fireEvent.click(await screen.findByRole("button", { name: "Use the default" }));
    await waitFor(() => expect(staff).toHaveBeenCalledWith("/admin/platform/legal-pages/privacy", { method: "DELETE" }));
  });
});
