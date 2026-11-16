import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, it, vi } from "vitest";
import { EquipmentKitManager } from "./EquipmentKitManager";

const api = vi.hoisted(() => ({ version: 1, detail: vi.fn(), save: vi.fn() }));
vi.mock("../inventory/useIntakeScope", () => ({ useIntakeScope: () => ({ context: "person", owner: "1" }) }));
vi.mock("../../lib/api/sessionTokens", () => ({ getSessionOwner: () => "1" }));
vi.mock("./StaffListContext", async () => { const React = await import("react"); return { StaffListContext: React.createContext({ actorId: 1 }) }; });
vi.mock("./KitProductPicker", () => ({ KitProductPicker: () => null }));
vi.mock("../inventory/equipmentKitsApi", () => ({
  staffKits: async () => ({ count: 1, next: null, previous: null, results: [{ id: 3, name: "Kit", revision: api.version, current_version: api.version, published_for_contexts: true, archived: false }] }),
  staffKit: () => api.detail(), createKitVersion: (...args: unknown[]) => api.save(...args),
  archiveKit: vi.fn(), createKit: vi.fn(), publishKit: vi.fn(),
}));

it("loads the newly saved version when reopened and keeps the submitted edit", async () => {
  api.version = 1; api.detail.mockReset(); api.save.mockReset();
  api.detail.mockImplementation(async () => ({ id: 3, name: "Kit", revision: api.version, current_version: api.version, published_for_contexts: true, archived: false, lines: [{ product_id: api.version === 1 ? 11 : 22, quantity_per_person: 1, kind: "returnable" }] }));
  api.save.mockImplementation(async () => { api.version = 2; });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  render(<QueryClientProvider client={client}><EquipmentKitManager tenant={4} canEdit /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole("button", { name: "View" }));
  await screen.findByText(/#11 · 1/);
  fireEvent.click(screen.getByRole("button", { name: "Save kit" }));
  await screen.findByText("Kit saved.");
  fireEvent.click(screen.getByRole("button", { name: "View" }));
  await screen.findByText(/#22 · 1/);
  expect(screen.queryByText(/#11 · 1/)).toBeNull();
  await waitFor(() => expect(screen.getByRole("button", { name: "Save kit" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "Save kit" }));
  await waitFor(() => expect(api.save).toHaveBeenLastCalledWith(4, 3, 2, "Kit", [{ product_id: 22, quantity_per_person: 1, kind: "returnable" }]));
});
