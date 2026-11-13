import { describe, expect, it } from "vitest";

import { reorderPosition, splitByEstimate } from "./boardOrder";
import type { JobBoard, StaffJob } from "./machineJobsApi";

const job = (id: number, queued: string, extra: Partial<StaffJob> = {}) =>
  ({ id, queue_id: 1, status: "accepted", urgent: false, queued_at: queued, created_at: queued, estimated_minutes: 60, ...extra }) as StaffJob;

const board = (queue: StaffJob[], assigned: StaffJob[] = []): JobBoard => ({
  machine_type_id: 1, lanes: [{ machine_id: 9, machine_name: "P1", status: "idle", locked_out: false, running: [], assigned }],
  queue, review: [], waiting_on_member: [], ready: [], overdue_pickup_ids: [], no_show_member_ids: [],
});

describe("reorderPosition", () => {
  const a = job(1, "2026-11-01T10:00:00Z"), b = job(2, "2026-11-01T11:00:00Z"), c = job(3, "2026-11-01T12:00:00Z");

  it("places the job just before the neighbour above and after the one below", () => {
    const data = board([a, b, c]);
    expect(reorderPosition(b, "up", data.queue, data)).toBe(1);
    expect(reorderPosition(b, "down", data.queue, data)).toBe(3);
    expect(reorderPosition(c, "up", data.queue, data)).toBe(2);
  });

  it("counts jobs pre-assigned to a machine, which the server orders among the same peers", () => {
    const early = job(4, "2026-11-01T09:00:00Z");
    const data = board([a, b, c], [early]);
    expect(reorderPosition(b, "up", data.queue, data)).toBe(2);
  });

  it("cannot move past the end or across urgency", () => {
    const urgent = job(5, "2026-11-01T08:00:00Z", { urgent: true });
    const data = board([urgent, a, b]);
    expect(reorderPosition(a, "up", data.queue, data)).toBeNull();
    expect(reorderPosition(b, "down", data.queue, data)).toBeNull();
  });
});

describe("splitByEstimate", () => {
  it("splits a total by each job's estimate share", () => {
    expect(splitByEstimate([{ id: 1, estimated_minutes: 30 }, { id: 2, estimated_minutes: 90 }], 100)).toEqual({ 1: 25, 2: 75 });
  });
});
