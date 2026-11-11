import { afterEach, expect, it, vi } from "vitest";
const fence = vi.hoisted(() => ({ suspendPushForRefresh: vi.fn(), resumePushAfterRefresh: vi.fn(), freezeBeforeAuthMutation: vi.fn() }));
vi.mock("./authFreeze", () => fence);
import { refreshAccessToken } from "./sessionTokens";

afterEach(() => { vi.unstubAllGlobals(); vi.clearAllMocks(); });
it("does not send refresh until the push worker has suspended", async () => {
  let release!: (value: null) => void;
  fence.suspendPushForRefresh.mockReturnValue(new Promise(resolve => { release = resolve; }));
  const fetcher = vi.fn().mockResolvedValue(new Response("{}", { status: 401 })); vi.stubGlobal("fetch", fetcher);
  const pending = refreshAccessToken("person"); await Promise.resolve(); expect(fetcher).not.toHaveBeenCalled();
  release(null); await expect(pending).resolves.toBe(false); expect(fetcher).toHaveBeenCalledTimes(1);
});
