import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";
import source from "./useStaffScanner.ts?raw";
import { useStaffScanner } from "./useStaffScanner";
import type { Makerspace } from "./shared";

const { request } = vi.hoisted(() => ({ request: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest: request }));
vi.mock("./shared", () => ({ useStaffGet: (_key: unknown, path: string) => ({
  data: path === "/auth/me" ? { makerspaces: [{ id: 7, actions: ["manage_qr", "edit_inventory"] }] }
    : { results: [{ id: 21, name: "Target", tracking_mode: "individual" }] },
  isLoading: false, isError: false,
}) }));

const expected = {
  resolve: ["/admin/qr/resolve", { method: "POST", body: '{"payload":"token","makerspace_id":7}' }],
  revoke: ["/admin/qr/9/revoke", { method: "POST", body: "{}" }],
  loadContents: ["/admin/containers/31/contents"],
  rebind: ["/admin/qr/9/rebind-target", { method: "POST", body: '{"target_type":"product","target_id":21,"new_name":"Renamed"}' }],
  moveAsset: ["/admin/qr/9/rebind-target", { method: "POST",
    body: '{"target_type":"asset","target_id":31,"destination_makerspace_id":8,"destination_product_id":21,"new_name":"Moved unit"}' }],
} as const;
type Operation = keyof typeof expected;
const discovered = [...source.matchAll(/const\s+(\w+)\s*=\s*useMutation\(/g)].map(match => match[1]);
beforeEach(() => request.mockReset());

it("censuses all mutations in the actual scanner hook", () => {
  expect([...discovered].sort()).toEqual(Object.keys(expected).sort());
});

for (const operation of discovered as Operation[]) {
  for (const outcome of ["success", "refusal"] as const) {
    it(`${operation}: exact request, pending state, ${outcome} and refresh`, async () => {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
      const invalidated = vi.spyOn(client, "invalidateQueries");
      const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
      const resolved = { qr: { id: 9, makerspace: 7, payload: "token", status: "active" },
        target: { id: 31, type: operation === "moveAsset" ? "asset" : "product", name: "Meter", asset_tag: "Unit" },
        allowed_actions: ["view", "revoke"] };
      request.mockResolvedValue(resolved);
      const { result, unmount } = renderHook(() => useStaffScanner({
        makerspace: { id: 7 } as Makerspace, makerspaces: [], isSuperadmin: true,
      }), { wrapper });
      act(() => result.current.resolve.mutate("token"));
      await waitFor(() => expect(result.current.resolved?.qr.id).toBe(9));
      act(() => {
        result.current.setSelectedProductId("21"); result.current.setNewName(" Renamed ");
        result.current.setDestMakerspaceId("8"); result.current.setDestProductId("21");
        result.current.setMoveTag(" Moved unit "); result.current.setConfirmRevoke(true);
      });
      request.mockClear(); invalidated.mockClear();
      let resolve!: (value: unknown) => void;
      let reject!: (error: Error) => void;
      request.mockImplementationOnce(() => new Promise((yes, no) => { resolve = yes; reject = no; }));
      const invoke = {
        resolve: () => result.current.resolve.mutate(" token "),
        revoke: () => result.current.revoke.mutate(9),
        loadContents: () => result.current.loadContents.mutate(31),
        rebind: () => result.current.rebind.mutate(),
        moveAsset: () => result.current.moveAsset.mutate(),
      };
      act(invoke[operation]);
      await waitFor(() => expect(result.current[operation].isPending).toBe(true));
      expect(request.mock.calls).toEqual([expected[operation]]);
      expect(invalidated).not.toHaveBeenCalled();
      const refusal = new Error("This command is not permitted.");
      await act(async () => {
        if (outcome === "refusal") reject(refusal);
        else resolve(operation === "loadContents" ? { products: [], assets: [] } : resolved);
      });
      await waitFor(() => expect(result.current[operation].status).toBe(outcome === "success" ? "success" : "error"));
      if (outcome === "refusal") {
        expect(result.current[operation].error).toBe(refusal);
        expect(invalidated).not.toHaveBeenCalled();
        expect(result.current.resolved?.qr.id).toBe(9);
        expect(request.mock.calls).toEqual([expected[operation]]);
      } else if (["revoke", "rebind", "moveAsset"].includes(operation)) {
        expect(invalidated).toHaveBeenCalled();
        await waitFor(() => expect(request.mock.calls).toEqual([
          expected[operation], ["/admin/qr/resolve", { method: "POST", body: '{"payload":"token","makerspace_id":7}' }],
        ]));
      } else {
        expect(invalidated).not.toHaveBeenCalled();
        expect(request.mock.calls).toEqual([expected[operation]]);
      }
      unmount(); client.clear();
    });
  }
}
