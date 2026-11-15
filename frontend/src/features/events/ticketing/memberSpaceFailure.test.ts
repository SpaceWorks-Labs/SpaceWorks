import { describe, expect, it, vi } from "vitest";

import { StructuredApiError } from "../../../lib/api";
import { memberSpaceFailure } from "./memberSpaceFailure";

const outage = () => new StructuredApiError(503, { code: "service_unavailable", detail: "The space is down." });

describe("memberSpaceFailure", () => {
  it("is no failure while the space loads cleanly", () => {
    expect(memberSpaceFailure({ makerspaceId: 0, error: null })).toBeUndefined();
  });

  it("turns an outage with no cached space into an error with a Retry that refetches the space", () => {
    const refetch = vi.fn();
    const state = memberSpaceFailure({ makerspaceId: 0, error: outage(), refetch });
    expect(state).toEqual({ status: "error", error: "The space is down.", onRetry: expect.any(Function) });
    state!.onRetry!();
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("keeps a refusal's explanation with no Retry", () => {
    const refusal = new StructuredApiError(404, { code: "module_disabled", detail: "Events are switched off here." });
    expect(memberSpaceFailure({ makerspaceId: 0, error: refusal, refetch: vi.fn() }))
      .toEqual({ status: "error", error: "Events are switched off here.", onRetry: undefined });
  });

  // R9 review note D: a failed background refetch over cached bootstrap data keeps the working page.
  it("leaves the page alone when the space is cached and only a background refetch failed", () => {
    expect(memberSpaceFailure({ makerspaceId: 7, error: outage(), refetch: vi.fn() })).toBeUndefined();
  });
});
