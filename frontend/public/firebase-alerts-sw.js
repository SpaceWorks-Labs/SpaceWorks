/* Dedicated /firebase-alerts/ worker. No Firebase SW SDK: its onPush broadcasts to uncontrolled clients. */
let ownerEpoch = null, revision = 0, epochLoaded = false;
let bridgeId = null, ownerSpace = null, suspended = false, heldOwner = null, ticket = null;
const pending = new Map(), proved = new Map();
const bridgePath = "/firebase-alerts/setup";
function reply(event, value) { event.ports[0]?.postMessage(value); }
async function controlledBridge(id) {
  const clients = await self.clients.matchAll({ type: "window", includeUncontrolled: false });
  return clients.find(client => client.id === id && new URL(client.url).origin === self.location.origin && new URL(client.url).pathname === bridgePath);
}
function writeEpoch(value) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("spaceworks-firebase-alerts", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("state");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result, tx = db.transaction("state", "readwrite");
      if (value === null) tx.objectStore("state").delete("epoch"); else tx.objectStore("state").put(value, "epoch");
      tx.oncomplete = () => { db.close(); resolve(); }; tx.onerror = () => { db.close(); reject(tx.error); };
    };
  });
}
let writes = Promise.resolve();
function persistEpoch(value) {
  const next = writes.then(() => writeEpoch(value));
  writes = next.catch(() => undefined);
  return next;
}
function readEpoch() {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("spaceworks-firebase-alerts", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("state");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => { const db = open.result, tx = db.transaction("state", "readonly"), get = tx.objectStore("state").get("epoch"); tx.oncomplete = () => { const result = get.result; db.close(); resolve(result); }; tx.onerror = () => { db.close(); reject(tx.error); }; };
  });
}
function validOwner(value) { return value && typeof value.epoch === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.epoch); }
function loadEpoch() {
  if (epochLoaded) return Promise.resolve();
  const atStart = revision;
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("spaceworks-firebase-alerts", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("state");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const db = open.result, tx = db.transaction("state", "readonly"), get = tx.objectStore("state").get("epoch");
      tx.oncomplete = () => {
        const value = get.result;
        if (revision === atStart) { heldOwner = validOwner(value) && value.suspended === true ? value : null; suspended = Boolean(heldOwner); ownerEpoch = validOwner(value) && !suspended ? value.epoch : null; ownerSpace = validOwner(value) ? value.space : null; epochLoaded = true; }
        db.close(); resolve();
      };
      tx.onerror = () => { db.close(); reject(tx.error); };
    };
  });
}
self.addEventListener("message", event => {
  const data = event.data;
  if (!event.source?.id || event.source.type !== "window" || !data || typeof data !== "object") return;
  try { if (new URL(event.source.url).origin !== self.location.origin) return; } catch { return; }
  // Freeze immediately before awaiting any identity or storage work.
  if (data.kind === "freeze") { revision++; epochLoaded = true; ownerEpoch = null; ownerSpace = null; suspended = false; heldOwner = null; ticket = null; bridgeId = null; pending.clear(); proved.clear(); }
  if (data.kind === "suspend") { revision++; suspended = true; ticket = null; }
  const atStart = revision;
  event.waitUntil((async () => {
    if (data.kind === "suspend") {
      const source = await self.clients.get(event.source.id);
      if (!source || new URL(source.url).origin !== self.location.origin) return;
      const saved = epochLoaded ? (heldOwner ?? { epoch: ownerEpoch, space: ownerSpace }) : await readEpoch();
      if (revision !== atStart) { reply(event, { ok: false }); return; }
      ownerEpoch = null; ownerSpace = null; epochLoaded = true; heldOwner = validOwner(saved) ? saved : null;
      await persistEpoch(validOwner(saved) ? { epoch: saved.epoch, space: saved.space, suspended: true } : null);
      if (revision !== atStart || !validOwner(saved)) { reply(event, { ok: true }); return; }
      ticket = { id: crypto.randomUUID(), client: source.id, epoch: saved.epoch, space: saved.space, revision, expires: Date.now() + 30000 };
      reply(event, { ok: true, ticket: ticket.id, owner_epoch: ticket.epoch, makerspace_id: ticket.space }); return;
    }
    if (data.kind === "resume") {
      const source = await self.clients.get(event.source.id), current = ticket;
      if (!source || new URL(source.url).origin !== self.location.origin || !current || current.client !== source.id || current.id !== data.ticket || current.revision !== revision || current.expires < Date.now()) { reply(event, { ok: false }); return; }
      ticket = null; await persistEpoch({ epoch: current.epoch, space: current.space, suspended: false });
      if (revision !== atStart) { reply(event, { ok: false }); return; }
      ownerEpoch = current.epoch; ownerSpace = current.space; epochLoaded = true; suspended = false; heldOwner = null; reply(event, { ok: true }); return;
    }
    if (data.kind === "freeze") {
      const source = await self.clients.get(event.source.id);
      if (!source || new URL(source.url).origin !== self.location.origin) return;
      await persistEpoch(null); reply(event, { ok: true }); return;
    }
    const client = await controlledBridge(event.source.id);
    if (!client) return;
    if (data.kind === "expect" && typeof data.challenge === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.challenge)) {
      bridgeId = client.id; pending.set(data.challenge, client.id); reply(event, { ok: true }); return;
    }
    if (data.kind === "activate" && typeof data.owner_epoch === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(data.owner_epoch) && Number.isSafeInteger(data.space) && data.space > 0 && client.id === bridgeId && typeof data.challenge === "string") {
      const proof = proved.get(data.challenge);
      if (revision !== atStart || !proof || proof.client !== client.id || proof.expires < Date.now()) { reply(event, { ok: false }); return; }
      proved.delete(data.challenge);
      await persistEpoch({ epoch: data.owner_epoch, space: data.space, suspended: false }); if (revision !== atStart) { reply(event, { ok: false }); return; } revision++; ticket = null; ownerEpoch = data.owner_epoch; ownerSpace = data.space; epochLoaded = true; suspended = false; heldOwner = null; reply(event, { ok: true });
    }
  })().catch(() => reply(event, { ok: false })));
});
self.addEventListener("push", event => {
  event.waitUntil((async () => {
    let message; try { message = event.data?.json(); } catch { return; }
    if (!message || typeof message !== "object" || message.notification || !message.data || typeof message.data !== "object") return;
    const data = message.data;
    if (suspended && data.kind !== "spaceworks_fcm_challenge") return;
    if (data.kind === "spaceworks_inbox_changed") await loadEpoch();
    if (suspended && data.kind !== "spaceworks_fcm_challenge") return;
    const atStart = revision, client = bridgeId && await controlledBridge(bridgeId);
    if (atStart !== revision) return;
    if (client && data.kind === "spaceworks_fcm_challenge" && typeof data.challenge === "string" && typeof data.nonce === "string" && pending.get(data.challenge) === client.id) {
      pending.delete(data.challenge); proved.set(data.challenge, { client: client.id, expires: Date.now() + 30000 });
      client.postMessage({ kind: data.kind, challenge: data.challenge, nonce: data.nonce }); return;
    }
    if (data.kind === "spaceworks_inbox_changed" && ownerEpoch && data.owner_epoch === ownerEpoch) {
      if (client) client.postMessage({ kind: data.kind, owner_epoch: ownerEpoch });
      await self.registration.showNotification("Space Works", { body: "You have an update.", tag: "spaceworks-inbox", icon: "/member-pwa/icon-192.png" });
    }
  })());
});




self.addEventListener("notificationclick", event => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow(new URL("/member", self.location.origin).href));
});


self.addEventListener("install", event => { event.waitUntil(persistEpoch(null)); });






