import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it, vi } from "vitest";

it("rejects a stale A hint after the worker acknowledges an owner change to B", async () => {
  const handlers: Record<string, (event: any) => void> = {};
  const messages: unknown[] = [], notifications: unknown[] = [];
  const client = { id: "bridge", type: "window", url: "https://space.test/firebase-alerts/setup", postMessage: (value: unknown) => messages.push(value) };
  let stored: unknown;
  const indexedDB = { open() {
    const open: any = {};
    queueMicrotask(() => { open.result = { transaction() {
      const tx: any = { objectStore: () => ({ put(value: unknown) { stored = value; }, delete() { stored = undefined; }, get() { return { result: stored }; } }) };
      queueMicrotask(() => tx.oncomplete?.()); return tx;
    }, close() {} }; open.onsuccess(); }); return open;
  } };
  const worker = { location: { origin: "https://space.test" }, clients: { matchAll: async () => [client], get: async () => client, openWindow: vi.fn() }, registration: { showNotification: async (...args: unknown[]) => { notifications.push(args); } }, addEventListener: (type: string, fn: (event: any) => void) => { handlers[type] = fn; } };
  const source = readFileSync(resolve(process.cwd(), "public/firebase-alerts-sw.js"), "utf8");
  new Function("self", "indexedDB", source)(worker, indexedDB);
  const command = async (data: object) => { let task!: Promise<unknown>; let ack: unknown; handlers.message({ data, source: client, ports: [{ postMessage: (value: unknown) => { ack = value; } }], waitUntil: (value: Promise<unknown>) => { task = value; } }); await task; expect(ack).toEqual(expect.objectContaining({ ok: true })); return ack as { ok: boolean; ticket?: string }; };
  const challengePush = async (challenge: string) => { let task!: Promise<unknown>; handlers.push({ data: { json: () => ({ data: { kind: "spaceworks_fcm_challenge", challenge, nonce: "synthetic" } }) }, waitUntil: (value: Promise<unknown>) => { task = value; } }); await task; messages.length = 0; };
  const push = async (epoch: string) => { let task!: Promise<unknown>; handlers.push({ data: { json: () => ({ data: { kind: "spaceworks_inbox_changed", owner_epoch: epoch } }) }, waitUntil: (value: Promise<unknown>) => { task = value; } }); await task; };
  const a = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", challenge = "cccccccc-cccc-cccc-cccc-cccccccccccc";
  await command({ kind: "expect", challenge }); await challengePush(challenge); await command({ kind: "activate", owner_epoch: a, space: 7, challenge });
  const foreignWait = vi.fn(); handlers.message({ data: { kind: "freeze" }, source: { id: "foreign", type: "window", url: "https://evil.test/" }, ports: [], waitUntil: foreignWait });
  expect(foreignWait).not.toHaveBeenCalled();
  let deniedTask!: Promise<unknown>; let denial: unknown;
  handlers.message({ data: { kind: "activate", owner_epoch: a, space: 7, challenge }, source: client, ports: [{ postMessage: (value: unknown) => { denial = value; } }], waitUntil: (value: Promise<unknown>) => { deniedTask = value; } });
  await deniedTask; expect(denial).toEqual({ ok: false });
  await command({ kind: "suspend" }); await push(a); expect(messages).toEqual([]); expect(notifications).toEqual([]);
  await command({ kind: "freeze" });
  await command({ kind: "expect", challenge }); await challengePush(challenge); await command({ kind: "activate", owner_epoch: b, space: 7, challenge });
  await push(a); expect(messages).toEqual([]); await push(b); expect(messages).toEqual([{ kind: "spaceworks_inbox_changed", owner_epoch: b }]); expect(notifications).toHaveLength(1);
  let release!: (value: typeof client) => void; let delayed = true;
  worker.clients.get = async () => delayed ? (delayed = false, await new Promise<typeof client>(resolve => { release = resolve; })) : client;
  let stale!: Promise<unknown>; let staleReply: unknown;
  handlers.message({ data: { kind: "suspend" }, source: client, ports: [{ postMessage: (value: unknown) => { staleReply = value; } }], waitUntil: (value: Promise<unknown>) => { stale = value; } });
  const fresh = await command({ kind: "suspend" }); await command({ kind: "resume", ticket: fresh.ticket });
  release(client); await stale; expect(staleReply).toEqual({ ok: false });
  messages.length = 0; await push(b); expect(messages).toEqual([{ kind: "spaceworks_inbox_changed", owner_epoch: b }]); expect(notifications).toHaveLength(2);
});






it("keeps a suspended epoch across worker restart until a fresh same-client resume", async () => {
  let stored: unknown; const notices: unknown[] = [];
  const client = { id: "bridge", type: "window", url: "https://space.test/firebase-alerts/setup", postMessage: vi.fn() };
  const idb = { open() { const open: any = {}; queueMicrotask(() => { open.result = { transaction() { const tx: any = { objectStore: () => ({ put(value: unknown) { stored = value; }, delete() { stored = undefined; }, get() { return { result: stored }; } }) }; queueMicrotask(() => tx.oncomplete?.()); return tx; }, close() {} }; open.onsuccess(); }); return open; } };
  const source = readFileSync(resolve(process.cwd(), "public/firebase-alerts-sw.js"), "utf8");
  function newWorker() {
    const handlers: Record<string, (event: any) => void> = {};
    const worker = { location: { origin: "https://space.test" }, clients: { matchAll: async () => [client], get: async () => client, openWindow: vi.fn() }, registration: { showNotification: async (...args: unknown[]) => { notices.push(args); } }, addEventListener: (type: string, fn: (event: any) => void) => { handlers[type] = fn; } };
    new Function("self", "indexedDB", source)(worker, idb);
    return handlers;
  }
  async function command(handlers: Record<string, (event: any) => void>, data: object) {
    let task!: Promise<unknown>, result: any;
    handlers.message({ data, source: client, ports: [{ postMessage: (value: unknown) => { result = value; } }], waitUntil: (value: Promise<unknown>) => { task = value; } }); await task; return result;
  }
  async function push(handlers: Record<string, (event: any) => void>, data: object) { let task!: Promise<unknown>; handlers.push({ data: { json: () => ({ data }) }, waitUntil: (value: Promise<unknown>) => { task = value; } }); await task; }
  const epoch = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", challenge = "cccccccc-cccc-cccc-cccc-cccccccccccc";
  let worker = newWorker(); await command(worker, { kind: "expect", challenge });
  await push(worker, { kind: "spaceworks_fcm_challenge", challenge, nonce: "synthetic" });
  await command(worker, { kind: "activate", challenge, owner_epoch: epoch, space: 7 });
  await command(worker, { kind: "suspend" }); // refresh fails before server proof
  worker = newWorker(); await push(worker, { kind: "spaceworks_inbox_changed", owner_epoch: epoch }); expect(notices).toEqual([]);
  const again = await command(worker, { kind: "suspend" }); expect(again.owner_epoch).toBe(epoch);
  await command(worker, { kind: "resume", ticket: again.ticket });
  await push(worker, { kind: "spaceworks_inbox_changed", owner_epoch: epoch }); expect(notices).toHaveLength(1);
});

