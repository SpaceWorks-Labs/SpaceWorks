import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { BRAND_SURFACES, deriveBrandPalette } from "../../lib/brandColours";
import { PublicInventoryPage } from "./PublicInventoryPage";

const state = vi.hoisted(() => ({ theme: { primary_color: "#004400", accent_color: "#5a1633" }, mode: "central", inventoryError: false }));
vi.mock("../../lib/tenant", () => ({
  useTenant: () => ({ mode: state.mode, slug: "brand", modules: new Set(), bootstrap: { theme: state.theme, branding: {}, modules: [], makerspace: { name: "Brand Space" } } }),
  useTenantPath: () => (subpath = "") => `/m/brand/${subpath}`,
}));
vi.mock("./usePublicInventory", () => ({
  useTenantBootstrap: () => ({ data: { theme: state.theme, branding: {}, modules: [], makerspace: { name: "Brand Space" } } }),
  usePublicCategories: () => ({ data: [] }),
  usePublicInventory: () => ({ data: { results: [], count: 0 }, isError: state.inventoryError, refetch: vi.fn() }),
}));
// Request-form authentication is orthogonal to the routed page's token scope.
vi.mock("./PublicRequestPanel", () => ({ PublicRequestPanel: () => <p>Request panel content</p> }));

beforeEach(() => {
  state.theme = { primary_color: "#004400", accent_color: "#5a1633" };
  state.mode = "central";
  state.inventoryError = false;
  document.documentElement.className = "";
  vi.spyOn(window, "getComputedStyle").mockImplementation(() => ({
    getPropertyValue: (name: string) => {
      const mode = document.documentElement.classList.contains("dark") ? "dark" : "light";
      const tokens = { brand: "0 110 99", "on-brand": "255 244 232",
        bg: BRAND_SURFACES[mode][0].join(" "), surface: BRAND_SURFACES[mode][1].join(" "), panel: BRAND_SURFACES[mode][2].join(" "), hover: BRAND_SURFACES[mode][3].join(" ") };
      return tokens[name.replace("--color-", "") as keyof typeof tokens] ?? "";
    },
  }) as CSSStyleDeclaration);
});
afterEach(() => { vi.restoreAllMocks(); document.documentElement.className = ""; });

function show() {
  return render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><PublicInventoryPage /></MemoryRouter></QueryClientProvider>);
}

it.each(["central", "single"])("renders public derived fill, foreground and interaction tokens in %s mode", (mode) => {
  state.mode = mode;
  show();
  const main = screen.getByRole("main").closest("[style]") as HTMLElement;
  expect(main.style.getPropertyValue("--color-brand")).toBe("0 68 0");
  expect(main.style.getPropertyValue("--color-on-brand")).toBe("255 244 232");
  expect(main.style.getPropertyValue("--color-brand-hover")).toBe("26 86 23");
  expect(main.style.getPropertyValue("--color-brand-active")).toBe("51 103 46");
  expect(screen.getByRole("button", { name: "Search" })).toHaveClass("desk-button-brand");
  expect(document.documentElement.style.getPropertyValue("--color-brand")).toBe("");
  expect(main.style.getPropertyValue("--color-accent")).toBe("");
  expect(document.title).toBe("Inventory · Brand Space");
  expect(document.head.querySelector('meta[property="og:title"]')).toHaveAttribute("content", "Inventory · Brand Space");
  expect(document.head.querySelector('link[rel="canonical"]')).toHaveAttribute("href", `${window.location.origin}/m/brand/inventory`);
});

it("rederives ink when dark mode changes without recolouring the staff root", async () => {
  show();
  const main = screen.getByRole("main").closest("[style]") as HTMLElement;
  const lightInk = main.style.getPropertyValue("--color-brand-ink");
  act(() => document.documentElement.classList.add("dark"));
  const dark = deriveBrandPalette(state.theme, "dark");
  await waitFor(() => expect(main.style.getPropertyValue("--color-brand-ink")).toBe(dark.ink.join(" ")));
  expect(main.style.getPropertyValue("--color-brand-ink")).not.toBe(lightInk);
  expect(main.style.getPropertyValue("--color-on-brand")).toBe("255 244 232");
  expect(document.documentElement.style.getPropertyValue("--color-brand")).toBe("");
});

it("clears every override on tenant navigation to an invalid stored palette", () => {
  const view = show();
  state.theme = { primary_color: "red", accent_color: "#5a1633" };
  view.rerender(<QueryClientProvider client={new QueryClient()}><MemoryRouter><PublicInventoryPage /></MemoryRouter></QueryClientProvider>);
  expect((screen.getByRole("main").closest("[style]") as HTMLElement).style.length).toBe(0);
});

it("opens the mobile request sheet from the sticky review action", () => {
  show();
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect(screen.getByRole("dialog", { name: "Your request" })).toBeVisible();
  expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
});
it("composes the catalogue into a kiosk without another layout or heading", () => {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><PublicInventoryPage embedded={({ body, request }) => <>{body}{request}</>} /></MemoryRouter></QueryClientProvider>);
  expect(screen.queryByRole("heading", { level: 1 })).toBeNull();
  expect(screen.queryByRole("navigation", { name: "Public navigation" })).toBeNull();
  expect(screen.getByLabelText("Search inventory")).toBeVisible();
});

it("keeps search and the request sheet available when inventory cannot refresh", () => {
  state.inventoryError = true;
  show();
  expect(screen.getByText("Couldn't load inventory. Try again.")).toBeVisible();
  expect(screen.getByLabelText("Search inventory")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Review request" }));
  expect(screen.getByText("Request panel content")).toBeVisible();
});
