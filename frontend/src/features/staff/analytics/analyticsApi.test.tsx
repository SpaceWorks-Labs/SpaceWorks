import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { analyticsBase, analyticsKeys, useAnalyticsLogin } from "./analyticsApi";
import type { AnalyticsScope } from "./analyticsApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../../lib/api", () => ({ staffRequest }));

describe("analytics login mutations", () => {
  beforeEach(() => staffRequest.mockReset());

  it.each<AnalyticsScope>([{ kind: "space", makerspaceId: 7 }, { kind: "platform" }])(
    "sends exact confirmation for create in $kind scope and refreshes server state",
    async (scope) => {
      const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
      const invalidate = vi.spyOn(client, "invalidateQueries");
      const credentials = { role: "reader", password: "shown-once", host: "db", port: 5432,
        database: "spaceworks", schema: "spaceworks_analytics" };
      staffRequest.mockResolvedValue(credentials);
      const wrapper = ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      );
      const { result, unmount } = renderHook(() => useAnalyticsLogin(scope), { wrapper });

      await act(async () => {
        expect(await result.current.create.mutateAsync()).toEqual(credentials);
      });
      await waitFor(() => {
        expect(result.current.create.isSuccess).toBe(true);
        expect(result.current.create.data).toEqual(credentials);
      });

      expect(staffRequest.mock.calls).toEqual([
        [`${analyticsBase(scope)}/login`, { method: "POST", body: '{"confirm":true}' }],
      ]);
      expect(invalidate.mock.calls).toEqual([
        [{ queryKey: analyticsKeys.all(scope) }], [{ queryKey: ["audit"] }],
      ]);
      expect(client.getQueryCache().findAll()).toEqual([]);
      expect(result.current.create.data).toEqual(credentials);
      unmount();
      client.clear();
    },
  );
});
