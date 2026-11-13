import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { useEventAnalytics } from "./eventCommunicationsApi";
import { useCancelEvent, useCompleteEvent } from "./eventsApi";
import {
  useApproveEventRegistration, useCancelEventRegistration, useMarkEventAttended,
  usePromoteEventRegistration, useRegisterMemberForEvent, useRejectEventRegistration,
} from "./eventsRegistrationApi";

const { staffRequest } = vi.hoisted(() => ({ staffRequest: vi.fn() }));
vi.mock("../../lib/api", async () => ({
  ...await vi.importActual<typeof import("../../lib/api")>("../../lib/api"), staffRequest,
}));
beforeEach(() => { staffRequest.mockReset(); });

const actions = [
  ["attendance", () => { const mutation = useMarkEventAttended(7, 3); return () => mutation.mutateAsync(11); }],
  ["approval", () => { const mutation = useApproveEventRegistration(7, 3); return () => mutation.mutateAsync(11); }],
  ["cancellation", () => { const mutation = useCancelEventRegistration(7, 3); return () => mutation.mutateAsync(11); }],
  ["rejection", () => { const mutation = useRejectEventRegistration(7, 3); return () => mutation.mutateAsync(11); }],
  ["promotion", () => { const mutation = usePromoteEventRegistration(7, 3); return () => mutation.mutateAsync(11); }],
  ["registration", () => { const mutation = useRegisterMemberForEvent(7, 3); return () => mutation.mutateAsync({ member_id: 11 }); }],
  ["event cancellation", () => { const mutation = useCancelEvent(7, 3); return () => mutation.mutateAsync(); }],
  ["event completion", () => { const mutation = useCompleteEvent(7, 3); return () => mutation.mutateAsync(); }],
] as const;

it.each(actions)("refetches mounted analytics after %s", async (_, useAction) => {
  let reads = 0;
  const path = "/admin/makerspace/7/analytics/event-attendance?subject_kind=event&subject_id=3";
  staffRequest.mockImplementation((url: string) => Promise.resolve(
    url === path ? { typed_rows: [{ registrations: ++reads }] } : { id: 11 },
  ));
  const client = new QueryClient({ defaultOptions: {
    queries: { retry: false, staleTime: Infinity }, mutations: { retry: false },
  } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  const { result, unmount } = renderHook(() => ({ analytics: useEventAnalytics(7, 3), run: useAction() }), { wrapper });
  await waitFor(() => expect(result.current.analytics.query.data?.typed_rows).toEqual([{ registrations: 1 }]));
  await act(async () => { await result.current.run(); });
  await waitFor(() => expect(result.current.analytics.query.data?.typed_rows).toEqual([{ registrations: 2 }]));
  expect(staffRequest.mock.calls.filter(([url]) => url === path)).toHaveLength(2);
  unmount();
  client.clear();
});
