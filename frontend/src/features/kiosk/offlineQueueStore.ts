import { i18n } from "../../lib/i18n";
import { keyFor, readKey, requestValue, encryptBytes, decryptBytes, deleteScopes, expired } from "../../lib/encryptedIndexedDb";
import type { KioskBootstrap, KioskLease, KioskWorkPackage } from "./kioskApi";
import type { ReplayEnvelope } from "./kioskReplayApi";
import {
  kioskScope, MAX_PENDING_COMMANDS, MAX_EVIDENCE_BYTES, queueDeadline,
  type OfflineQueue, type LoadedWork, type LocalCommand,
} from "./offlineQueueTypes";
import {
  openQueueDb, withQueueLock, withReplayLock, readQueue, decodeQueue,
  encodeQueue, writeQueue, aad, type StoredRecord,
} from "./offlineQueueDb";

async function usingDb<T>(task: (db: IDBDatabase) => Promise<T>) {
  const db = await openQueueDb();
  try { return await task(db); } finally { db.close(); }
}

export function loadQueue(scope: string) {
  return withQueueLock(() => usingDb((db) => readQueue(db, scope)));
}

export async function saveWorkPackage(token: string, apiBase: string, session: KioskBootstrap,
  lease: KioskLease, work: KioskWorkPackage) {
  const scope = kioskScope(session, lease);
  return withQueueLock(() => usingDb(async (db) => {
    const state: OfflineQueue = await readQueue(db, scope) ?? {
      version: 1, scope, token, apiBase, session, lease, works: [], commands: [],
    };
    const existing = state.works.find((item) => item.work.kind === work.kind && item.work.id === work.id);
    if (existing && state.commands.some((cmd) => cmd.workPackageId === existing.id)) {
      throw new Error(i18n._({ id: "offline.aac5f60fd9e3", message: "Acknowledge this handover's queue before replacing its work package." }));
    }
    const loaded: LoadedWork = { id: crypto.randomUUID(), aggregateId: crypto.randomUUID(), work };
    state.works = [...state.works.filter((item) => item !== existing), loaded];
    if (expired(queueDeadline(state)) || work.command_age_limit_seconds <= 0 || work.evidence_max_bytes <= 0) {
      throw new Error(i18n._({ id: "offline.c4cf0f830fb6", message: "This handover has expired. Reconnect and load it again." }));
    }
    const key = await keyFor(db, scope);
    const row = await encodeQueue(key, state);
    await writeQueue(db, row);
    // Prove CryptoKey cloning/decryption before advertising offline readiness.
    if (!await readQueue(db, scope)) throw new Error(i18n._({ id: "offline.aa0465c018ad", message: "This browser cannot retain encrypted offline work." }));
    return state;
  }));
}

function checkSelectedCommand(loaded: LoadedWork, envelope: ReplayEnvelope) {
  const work = loaded.work;
  const valid = work.kind === "reviewed_request"
    ? ["assign_box", "reviewed_issue", "reviewed_return"].includes(envelope.kind)
      && "request_id" in envelope.payload && envelope.payload.request_id === work.id
    : work.kind === "direct_loan" && envelope.kind === "direct_return" && envelope.payload.loan_id === work.id;
  if (!valid) throw new Error(i18n._({ id: "offline.3a724a783232", message: "Offline work is limited to this loaded handover." }));
  if ((envelope.kind === "reviewed_return" || envelope.kind === "direct_return")
      && !("remark" in envelope.payload ? envelope.payload.remark.trim() : envelope.payload.notes.trim())) {
    throw new Error(i18n._({ id: "offline.dc3f4eadbc42", message: "A return remark is required." }));
  }
}

export function enqueueCommand(scope: string, workId: string, draft: ReplayEnvelope, photo?: Blob, recoveryReplayId?: string) {
  return withQueueLock(() => usingDb(async (db) => {
    const state = await readQueue(db, scope);
    const loaded = state?.works.find((item) => item.id === workId);
    if (!state || !loaded) throw new Error(i18n._({ id: "offline.e383979a142c", message: "Reconnect to unlock and load this handover." }));
    checkSelectedCommand(loaded, draft);
    if (!state.lease.permitted_operations.includes(draft.kind)) throw new Error(i18n._({ id: "offline.183f6fff829e", message: "This lease cannot queue that operation." }));
    const stream = state.commands.filter((item) => item.envelope.aggregate_id === loaded.aggregateId);
    const previous = stream[stream.length - 1];
    if (previous?.status === "failed") throw new Error(i18n._({ id: "offline.8636b43f045d", message: "This handover needs staff resolution before more work can be queued." }));
    const envelope = { ...draft, aggregate_id: loaded.aggregateId, sequence: stream.length + 1,
      predecessor_client_id: previous?.envelope.client_command_id ?? null,
      client_created_at: new Date().toISOString() } as ReplayEnvelope;
    if (draft.kind !== "assign_box" && (!photo || !draft.evidence || photo.size < 1
      || photo.size > loaded.work.evidence_max_bytes || photo.type !== draft.evidence.content_type
      || photo.size !== draft.evidence.size_bytes)) throw new Error(i18n._({ id: "offline.d996a88612b6", message: "Capture a valid, bounded evidence photo first." }));
    const rows = await requestValue(db.transaction("records").objectStore("records").getAll()) as StoredRecord[];
    let pending = 0;
    for (const row of rows) {
      if (expired(row.expiresAt)) continue;
      const queue = await decodeQueue(db, row);
      pending += queue?.commands.filter((cmd) => cmd.status !== "succeeded").length ?? 0;
    }
    if (pending >= MAX_PENDING_COMMANDS) throw new Error(i18n._({ id: "offline.c8007099c2f5", message: "Queue limit reached (50). Reconnect before capturing more work." }));
    const key = await readKey(db, scope);
    if (!key) throw new Error(i18n._({ id: "offline.cc6572c83c91", message: "Offline key is missing. Reconnect to load the handover." }));
    const evidenceId = photo ? crypto.randomUUID() : null;
    const evidence = photo && evidenceId ? { ...await encryptBytes(key, await photo.arrayBuffer(), aad(scope, "evidence", evidenceId)),
      scope, id: evidenceId, expiresAt: queueDeadline(state), bytes: photo.size + 16 } : undefined;
    const images = await requestValue(db.transaction("evidence").objectStore("evidence").getAll()) as StoredRecord[];
    if (images.reduce((sum, item) => sum + item.bytes, 0) + (evidence?.bytes ?? 0) > MAX_EVIDENCE_BYTES) {
      throw new Error(i18n._({ id: "offline.fd513aacf994", message: "Encrypted photo queue limit reached (100 MiB). Nothing was dropped." }));
    }
    const command: LocalCommand = { envelope, workPackageId: loaded.id, evidenceRecordId: evidenceId,
      status: "queued", attempts: 0, nextRetryAt: 0, lastFailure: null, result: null, uploaded: false,
      ...(recoveryReplayId ? { recoveryReplayId } : {}) };
    state.commands.push(command);
    if (expired(queueDeadline(state))) throw new Error(i18n._({ id: "offline.5927d18dcb8c", message: "This handover expired before capture completed." }));
    await writeQueue(db, await encodeQueue(key, state), evidence);
    return state;
  }));
}

// Updates never recreate a wiped scope/key after an asynchronous network response.
export function updateCommand(scope: string, id: string, patch: Partial<LocalCommand>) {
  return withQueueLock(() => usingDb(async (db) => {
    const state = await readQueue(db, scope);
    const command = state?.commands.find((cmd) => cmd.envelope.client_command_id === id);
    const key = await readKey(db, scope);
    if (!state || !command || !key) return null;
    Object.assign(command, patch, { envelope: command.envelope });
    await writeQueue(db, await encodeQueue(key, state));
    return state;
  }));
}

export function readEvidence(scope: string, id: string) {
  return withQueueLock(() => usingDb(async (db) => {
    if (!await readQueue(db, scope)) throw new Error(i18n._({ id: "offline.675f049d1b10", message: "Offline work expired." }));
    const key = await readKey(db, scope);
    const row = await requestValue(db.transaction("evidence").objectStore("evidence").get(id)) as StoredRecord | undefined;
    if (!key || !row || row.scope !== scope) throw new Error(i18n._({ id: "offline.298c67a7fe65", message: "Offline evidence is missing." }));
    return decryptBytes(key, row, aad(scope, "evidence", id));
  }));
}

export function listQueues() {
  return withQueueLock(() => usingDb(async (db) => {
    const rows = await requestValue(db.transaction("records").objectStore("records").getAll()) as StoredRecord[];
    await deleteScopes(db, ["records", "evidence"], rows.filter((row) => expired(row.expiresAt)).map((row) => row.scope));
    const states = await Promise.all(rows.filter((row) => !expired(row.expiresAt)).map((row) => decodeQueue(db, row)));
    return states.filter((state): state is OfflineQueue => state !== null);
  }));
}

export const pruneKioskQueues = async () => { await listQueues(); };

// Caller already holds the replay lock; exported for the replay authority boundary.
export function destroyQueue(scope: string) {
  return withQueueLock(() => usingDb((db) => deleteScopes(db, ["records", "evidence"], [scope])));
}
export const wipeQueue = (scope: string) => withReplayLock(scope, () => destroyQueue(scope));
