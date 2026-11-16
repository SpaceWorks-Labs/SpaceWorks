// Browser notifications only (R2 L2, X38). Registered at its own narrow scope so it never
// controls a page, caches nothing and fetches nothing: it shows the inbox message the
// server encrypted for this browser and opens the in-app link on click.
self.addEventListener("push", event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch { data = {}; }
  const title = typeof data.title === "string" && data.title ? data.title.slice(0, 120) : "Space Works";
  event.waitUntil(self.registration.showNotification(title, {
    body: typeof data.body === "string" ? data.body.slice(0, 240) : "",
    tag: typeof data.tag === "string" ? data.tag : undefined,
    icon: "/member-pwa/icon-192.png",
    data: { url: typeof data.url === "string" && data.url.startsWith("/") ? data.url : "/" },
  }));
});
self.addEventListener("notificationclick", event => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin).href;
  event.waitUntil(self.clients.openWindow(url));
});
