import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api/errors";
import { ShelfChecksPanel } from "./ShelfChecksPanel";
import { ShowOnShelf } from "./ShowOnShelf";
import { StocktakeShelfGuide } from "./StocktakeShelfGuide";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", async original => ({ ...(await original<object>()), staffRequest }));

const wrap = (node: React.ReactNode) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{node}</QueryClientProvider>);
const calls = (needle: string) => staffRequest.mock.calls.filter(([path]) => String(path).includes(needle));

beforeEach(() => { staffRequest.mockReset(); staffRequest.mockImplementation(async () => ({})); });

describe("ShowOnShelf", () => {
  it("shows nothing when no pointer covers the target", async () => {
    staffRequest.mockResolvedValue({ results: [{ target_type: "item", target_id: "5", covered: false }] });
    wrap(<ShowOnShelf makerspaceId={1} targetType="item" targetId={5} />);
    await waitFor(() => expect(calls("coverage")).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Show on shelf" })).toBeNull();
  });

  it("shows nothing when the integrations switch is off (404)", async () => {
    staffRequest.mockImplementation(async () => { throw new StructuredApiError(404, { detail: "Not found." }); });
    wrap(<ShowOnShelf makerspaceId={1} targetType="box" targetId={9} />);
    await waitFor(() => expect(calls("coverage")).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Show on shelf" })).toBeNull();
  });

  it("points and clears when covered, sending only the target", async () => {
    staffRequest.mockImplementation(async (path: string) => path.endsWith("/coverage") ? { results: [{ target_type: "item", target_id: "5", covered: true }] } : { sent: 1 });
    wrap(<ShowOnShelf makerspaceId={1} targetType="item" targetId={5} />);
    fireEvent.click(await screen.findByRole("button", { name: "Show on shelf" }));
    await waitFor(() => expect(calls("/shelf-pointer/show")).toHaveLength(1));
    expect(JSON.parse(calls("/shelf-pointer/show")[0][1].body)).toEqual({ target_type: "item", target_id: "5" });
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(calls("/shelf-pointer/clear")).toHaveLength(1));
  });
});

describe("ShelfChecksPanel", () => {
  it("marks locations and saves one shelf check with notes", async () => {
    staffRequest.mockImplementation(async (path: string, init?: { method?: string }) => {
      if (path.includes("/shelf-pointer/locations")) return [{ location: "Shelf A", item_count: 2, covered: true }, { location: "Shelf B", item_count: 1, covered: false }];
      if (path.endsWith("/shelf-checks") && init?.method === "POST") return { id: "c1", scope_label: "", ok_count: 1, attention_count: 1, checked_by_name: "", created_at: new Date().toISOString(), entries: [] };
      if (path.endsWith("/shelf-checks")) return { count: 0, next: null, previous: null, results: [] };
      return {};
    });
    wrap(<ShelfChecksPanel makerspaceId={1} />);
    await screen.findByText("Shelf A");
    const save = screen.getByRole("button", { name: /Save shelf check/ });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    const [okA, , , attentionB] = [...screen.getAllByRole("button", { name: /^(OK|Needs attention)$/ })];
    fireEvent.click(okA);
    fireEvent.click(attentionB);
    fireEvent.change(await screen.findByLabelText("Note for Shelf B"), { target: { value: "Bin 3 empty" } });
    fireEvent.click(screen.getByRole("button", { name: /Save shelf check/ }));
    await waitFor(() => expect(staffRequest.mock.calls.some(([path, init]) => String(path).endsWith("/shelf-checks") && init?.method === "POST")).toBe(true));
    const post = staffRequest.mock.calls.find(([path, init]) => String(path).endsWith("/shelf-checks") && init?.method === "POST")!;
    expect(JSON.parse(post[1].body).entries).toEqual([{ location: "Shelf A", status: "ok", note: "" }, { location: "Shelf B", status: "attention", note: "Bin 3 empty" }]);
  });
});

describe("StocktakeShelfGuide", () => {
  const products = [{ id: 1, name: "Resistors", storage_location: "Shelf A" }, { id: 2, name: "Bolts", storage_location: "Shelf B" }];
  const respond = () => staffRequest.mockImplementation(async (path: string) => path.includes("/locations") ? [{ location: "Shelf A", item_count: 1, covered: true }, { location: "Shelf B", item_count: 1, covered: false }] : { sent: 1 });

  it("points at the first uncounted shelf", async () => {
    respond();
    wrap(<StocktakeShelfGuide makerspaceId={1} products={products} counted={new Set()} />);
    fireEvent.click(await screen.findByRole("button", { name: "Guide with the pointer" }));
    await screen.findByText("Shelf A");
    await waitFor(() => expect(calls("/shelf-pointer/show")).toHaveLength(1));
    expect(JSON.parse(calls("/shelf-pointer/show")[0][1].body).target_id).toBe("Shelf A");
  });

  it("moves on to the next shelf once the first is counted and flags a shelf with no saved position", async () => {
    respond();
    wrap(<StocktakeShelfGuide makerspaceId={1} products={products} counted={new Set([1])} />);
    fireEvent.click(await screen.findByRole("button", { name: "Guide with the pointer" }));
    await screen.findByText("Shelf B");
    expect(screen.getByText(/No pointer position saved/)).toBeTruthy();
    expect(calls("/shelf-pointer/show")).toHaveLength(0);
  });

  it("stays out of the way when the space has no pointer", async () => {
    staffRequest.mockImplementation(async () => { throw new StructuredApiError(404, { detail: "Not found." }); });
    wrap(<StocktakeShelfGuide makerspaceId={1} products={products} counted={new Set()} />);
    await waitFor(() => expect(calls("/locations")).toHaveLength(1));
    expect(screen.queryByRole("button", { name: "Guide with the pointer" })).toBeNull();
  });
});
