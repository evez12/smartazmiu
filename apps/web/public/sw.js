// Service worker for Web Push only; offline caching arrives with the PWA work (Sprint 15).
self.addEventListener("push", (event) => {
  if (!event.data) return;
  const message = event.data.json();
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      icon: "/icon.svg",
      lang: "az",
      tag: message.tag,
      data: { url: message.url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url ?? "/", self.location.origin);
  // Only same-origin paths: the payload comes from our server, but a link never leaves the site.
  const target = url.origin === self.location.origin ? url.href : self.location.origin;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      const open = windows.find((client) => client.url === target);
      return open ? open.focus() : self.clients.openWindow(target);
    }),
  );
});
