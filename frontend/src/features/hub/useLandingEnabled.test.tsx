import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useLandingEnabled } from "./useLandingEnabled";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../lib/api", () => ({ publicV1Request: request }));

let client: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;

beforeEach(() => { request.mockReset(); client = new QueryClient({ defaultOptions: { queries: { retry: false } } }); });

describe("useLandingEnabled", () => {
  it("is loading until the public config answers", async () => {
    request.mockResolvedValue({ landing_enabled: false });
    const { result } = renderHook(() => useLandingEnabled(), { wrapper });
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current).toEqual({ loading: false, enabled: false }));
    expect(request).toHaveBeenCalledWith("/config");
  });

  it("reads true from the config", async () => {
    request.mockResolvedValue({ landing_enabled: true });
    const { result } = renderHook(() => useLandingEnabled(), { wrapper });
    await waitFor(() => expect(result.current).toEqual({ loading: false, enabled: true }));
  });

  it("falls back to the default (on) when the field or the config is missing", async () => {
    request.mockImplementation(() => Promise.reject(new Error("offline")));
    const { result } = renderHook(() => useLandingEnabled(), { wrapper });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.enabled).toBe(true);
  });
});
