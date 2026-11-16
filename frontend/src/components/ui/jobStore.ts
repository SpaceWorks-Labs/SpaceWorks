import { currentSessionContext } from "../../lib/api/sessionContext";
export type TrayJob = { key: string; label: string; makerspaceId: number; endpoint: string; status: string; collectionId?: string; session?: number };
let nextSession = 0;
const states = new Map<string, { rows: TrayJob[]; session: number }>();
const state = (context = currentSessionContext()) => {
  if (!states.has(context)) states.set(context, { rows: [], session: ++nextSession });
  return states.get(context)!;
};
export const getJobSession = () => state().session;
const listeners = new Set<() => void>();
const publish = () => listeners.forEach(listener => listener());
export const jobStore = {
  subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
  snapshot: () => state().rows,
};
export const jobRunning = (status: string) => ["pending", "queued", "running", "building", "promoting"].includes(status);
export function trackJob(job: TrayJob, startedSession = state().session) {
  if (startedSession !== state().session) return;
  state().rows = [...state().rows.filter(row => row.key !== job.key), { ...job, session: state().session }].slice(-30); publish();
}
export function updateJob(key: string, status: string, startedSession = state().session) {
  if (startedSession !== state().session) return;
  if (state().rows.find(row => row.key === key)?.status === status) return;
  state().rows = state().rows.map(row => row.key === key ? { ...row, status } : row); publish();
}
export function dismissJob(key: string) { state().rows = state().rows.filter(row => row.key !== key); publish(); }
export function clearJobs(context = currentSessionContext()) { const value = state(context); value.session = ++nextSession; value.rows = []; publish(); }
