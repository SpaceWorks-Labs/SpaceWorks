import type { ReactNode } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, it, vi } from "vitest";
import source from "./useQrBatchBuilder.ts?raw";
import { useQrBatchBuilder } from "./useQrBatchBuilder";
import type { Makerspace } from "./shared";

const mocks = vi.hoisted(() => ({ request: vi.fn(), download: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: mocks.request, downloadStaffFile: mocks.download }));
vi.mock("./shared", () => ({ useStaffGet: (_key: unknown, path: string) => ({
  data: path.includes("/inventory?page") ? { results: [
    { id: 1, name: "Meter", tracking_mode: "quantity", is_archived: false },
    { id: 2, name: "Unit parent", tracking_mode: "individual", is_archived: false },
  ] } : path.includes("/assets") ? { results: [{ id: 5, asset_tag: "Unit Ω", status: "available" }] }
    : path.endsWith("qr-print-batches") ? { results: [] }
    : { id: 3, title: "Retained", items: [] },
  isLoading: false, isError: false,
}) }));

const cases = {
  createBatch: [["/admin/makerspace/7/qr-print-batches", { method: "POST", body: '{"title":"QR labels"}' }]],
  addProduct: [["/admin/qr/tools", { method: "POST", body: '{"makerspace_id":7,"product_id":1}' }],
    ["/admin/qr-print-batches/3/items", { method: "POST", body: '{"qr_code_id":9,"label_text":"Meter"}' }]],
  reprintAsset: [["/admin/assets/5/qr", { method: "POST", body: "{}" }],
    ["/admin/qr-print-batches/3/items", { method: "POST", body: '{"qr_code_id":9,"label_text":"Unit Ω"}' }]],
  generateAssets: [["/admin/products/2/assets/generate", { method: "POST",
    body: '{"count":50,"name_prefix":"Unit parent","print_batch_id":3}' }]],
  downloadZip: [["/admin/qr-print-batches/3/download", "qr-batch-3.zip"]],
} as const;
type Operation = keyof typeof cases;
const discovered = [...source.matchAll(/const\s+(\w+)\s*=\s*useMutation\(/g)].map(match => match[1]);

beforeEach(() => { mocks.request.mockReset(); mocks.download.mockReset(); });

it("has a state and transport case for every mutation declared by the real hook", () => {
  expect([...discovered].sort()).toEqual(Object.keys(cases).sort());
});

for (const operation of discovered as Operation[]) {
  for (const outcome of ["success", "refusal"] as const) {
    it(`${operation}: pending, ${outcome}, exact requests and cache refresh`, async () => {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
      const invalidated = vi.spyOn(client, "invalidateQueries");
      const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={["/?batch=3"]}>
        <QueryClientProvider client={client}>{children}</QueryClientProvider></MemoryRouter>;
      const { result, unmount } = renderHook(() => useQrBatchBuilder({
        makerspace: { id: 7, enabled_modules: ["asset_units", "qr_print_batches"] } as Makerspace,
      }), { wrapper });
      act(() => {
        result.current.selectProduct(operation === "reprintAsset" || operation === "generateAssets" ? "2" : "1");
        result.current.setAssetId("5");
        result.current.setBatchModalOpen(true);
      });
      let resolve!: (value: unknown) => void;
      let reject!: (error: Error) => void;
      const deferred = new Promise((yes, no) => { resolve = yes; reject = no; });
      const transport = operation === "downloadZip" ? mocks.download : mocks.request;
      transport.mockImplementationOnce(() => deferred);
      mocks.request.mockResolvedValue({ id: 9 });
      act(() => result.current[operation].mutate());
      await waitFor(() => expect(result.current[operation].isPending).toBe(true));
      expect(invalidated).not.toHaveBeenCalled();
      const refusal = new Error("The QR print batch is disabled.");
      act(() => { if (outcome === "refusal") reject(refusal); else resolve({ id: operation === "createBatch" ? 3 : 9 }); });
      await waitFor(() => expect(result.current[operation].status).toBe(outcome === "success" ? "success" : "error"));
      expect(transport.mock.calls).toEqual(outcome === "success" ? cases[operation] : cases[operation].slice(0, 1));
      if (outcome === "refusal") {
        expect(result.current[operation].error).toBe(refusal);
        expect(result.current.batchId).toBe("3");
        expect(result.current.batchModalOpen).toBe(true);
        expect(invalidated).not.toHaveBeenCalled();
      } else if (operation !== "downloadZip") {
        expect(invalidated).toHaveBeenCalledWith({ queryKey: ["qr-batches", 7] });
        expect(invalidated).toHaveBeenCalledWith({ queryKey: ["qr-batch", 3] });
        if (operation === "createBatch") expect(result.current.batchModalOpen).toBe(false);
      } else {
        expect(invalidated).not.toHaveBeenCalled();
      }
      unmount();
      client.clear();
    });
  }
}
