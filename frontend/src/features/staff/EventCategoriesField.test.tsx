import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../lib/api";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../lib/api", async () => ({ ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest: request }));

import { EventCategoriesField } from "./EventCategoriesField";

const path = "/admin/makerspaces/3/event-categories/";
let deleteResult: () => Promise<unknown>;
function setup(onChange = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><EventCategoriesField makerspaceId={3} value={8} onChange={onChange} /></QueryClientProvider>);
  return onChange;
}

beforeEach(() => {
  request.mockReset();
  deleteResult = () => Promise.resolve(undefined);
  request.mockImplementation((url: string, options?: RequestInit) => {
    if (url.startsWith(`${path}?page=`)) return Promise.resolve({ count: 1, next: null, previous: null, results: [{ id: 8, name: "Workshops", slug: "workshops", event_count: 3 }] });
    if (options?.method === "DELETE") return deleteResult();
    if (options?.method === "PATCH") return Promise.resolve({ id: 8, name: "Classes", slug: "classes" });
    return Promise.resolve({});
  });
});

describe("event categories", () => {
  it("renames a category with only the changed fields", async () => {
    setup();
    fireEvent.click(screen.getByText("Manage categories"));
    fireEvent.click(await screen.findByRole("button", { name: "Rename Workshops" }));
    expect(screen.getByText(/3 events/)).toBeVisible();
    fireEvent.change(screen.getAllByLabelText("Category name").at(-1)!, { target: { value: "Classes" } });
    fireEvent.click(screen.getByRole("button", { name: "Save category" }));
    await waitFor(() => expect(request).toHaveBeenCalledWith(`${path}8/`, { method: "PATCH", body: JSON.stringify({ name: "Classes" }) }));
  });

  it("explains a 409 when events still use the category", async () => {
    deleteResult = () => Promise.reject(new StructuredApiError(409, { detail: "Events use this category.", code: "category_referenced" }));
    const onChange = setup();
    fireEvent.click(screen.getByText("Manage categories"));
    fireEvent.click(await screen.findByRole("button", { name: "Delete Workshops" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete category" }));
    expect(await screen.findByText("Events use this category.")).toBeVisible();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("clears the selection when the selected category is deleted", async () => {
    const onChange = setup();
    fireEvent.click(screen.getByText("Manage categories"));
    fireEvent.click(await screen.findByRole("button", { name: "Delete Workshops" }));
    fireEvent.click(await screen.findByRole("button", { name: "Delete category" }));
    await waitFor(() => expect(onChange).toHaveBeenCalledWith(null));
    expect(request).toHaveBeenCalledWith(`${path}8/`, { method: "DELETE" });
  });
});
