import type { JobBoard, StaffJob } from "./machineJobsApi";

const anchor = (job: StaffJob) => job.queued_at ?? job.created_at;
const samePeers = (a: StaffJob, b: StaffJob) => a.queue_id === b.queue_id && !!a.urgent === !!b.urgent;

/** Every waiting (accepted) job on the board: the unassigned queue plus the jobs pre-assigned to a lane. */
export function acceptedJobs(board: JobBoard): StaffJob[] {
  return [...board.queue, ...board.lanes.flatMap(lane => lane.assigned)];
}

/**
 * The 1-based `position` the reorder endpoint needs to move `job` one place up or down in `column`.
 *
 * The server places a job among its queue's same-urgency ACCEPTED peers ordered by anchor (queued_at,
 * else created_at) then id, excluding the job itself -- pre-assigned jobs included. The visible
 * neighbour is located in that same ordering, so the move lands exactly next to it. Null when the
 * job cannot move that way (no same-urgency neighbour in the column).
 */
export function reorderPosition(job: StaffJob, direction: "up" | "down", column: StaffJob[], board: JobBoard): number | null {
  const index = column.findIndex(row => row.id === job.id);
  const neighbour = column[direction === "up" ? index - 1 : index + 1];
  if (index < 0 || !neighbour || !samePeers(job, neighbour)) return null;
  const peers = acceptedJobs(board).filter(row => row.id !== job.id && samePeers(job, row))
    .sort((a, b) => anchor(a).localeCompare(anchor(b)) || a.id - b.id);
  const at = peers.findIndex(row => row.id === neighbour.id);
  if (at < 0) return null;
  return direction === "up" ? at + 1 : at + 2;
}

/**
 * The 1-based `position` for dropping `job` onto `target`'s card in `column` (#141 drag to reorder):
 * dragged upwards it lands just before the target, downwards just after it -- the same placement the
 * move buttons use. Null when the drop is not allowed (itself, another queue or another urgency).
 */
export function dropPosition(job: StaffJob, target: StaffJob, column: StaffJob[], board: JobBoard): number | null {
  const from = column.findIndex(row => row.id === job.id), to = column.findIndex(row => row.id === target.id);
  if (from < 0 || to < 0 || from === to || !samePeers(job, target)) return null;
  const peers = acceptedJobs(board).filter(row => row.id !== job.id && samePeers(job, row))
    .sort((a, b) => anchor(a).localeCompare(anchor(b)) || a.id - b.id);
  const at = peers.findIndex(row => row.id === target.id);
  if (at < 0) return null;
  return to < from ? at + 1 : at + 2;
}

/** Proportional split of a batch total by each job's estimate share, matching the server's default split. */
export function splitByEstimate(jobs: Pick<StaffJob, "id" | "estimated_minutes">[], total: number): Record<number, number> {
  const weights = jobs.map(job => job.estimated_minutes || 1);
  const whole = weights.reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(jobs.map((job, index) => [job.id, Math.round((total * weights[index] / whole) * 100) / 100]));
}
