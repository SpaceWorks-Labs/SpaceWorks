import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { expect, it, vi } from "vitest";
import { KitProductPicker } from "./KitProductPicker";
import type { KitLine } from "../inventory/equipmentKitsApi";
const mock = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", () => ({ staffRequest: mock.request }));

it("keeps selected returnable and consumable lines across paginated searches", async () => {
  mock.request.mockImplementation((url: string) => Promise.resolve(url.includes("page=2")
    ? { results: [{ id: 2, name: "Glue", is_consumable: true }], previous: "page1", next: null }
    : { results: [{ id: 1, name: "Drill", is_consumable: false }], previous: null, next: "page2" }));
  function Harness() { const [lines, setLines] = useState<KitLine[]>([]); return <><KitProductPicker tenant={4} scope="actor:4" lines={lines} onChange={setLines} /><output>{JSON.stringify(lines)}</output></>; }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>);
  fireEvent.click(await screen.findByLabelText("Drill"));
  fireEvent.click(screen.getByRole("button", { name: "Next" }));
  fireEvent.click(await screen.findByLabelText("Glue"));
  expect(screen.getByRole("status").textContent).toContain('"product_id":1');
  expect(screen.getByRole("status").textContent).toContain('"kind":"consumable"');
  fireEvent.click(screen.getByRole("button", { name: "Previous" }));
  expect(await screen.findByLabelText("Drill")).toBeChecked();
  fireEvent.change(screen.getByLabelText("Search inventory"), { target: { value: "drill" } });
  expect(await screen.findByLabelText("Drill")).toBeChecked();
  expect(mock.request).toHaveBeenCalledWith("/admin/makerspace/4/inventory?page=1&archived=false&ordering=name&q=drill");
});
