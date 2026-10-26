// Chat load test (Sprint 6, D-073): SOCKETS WebSockets held open, together sending RATE messages per second.
// Run through `make load` after `prepare.py up`; see the README section "Load test".
import { check } from "k6";
import http from "k6/http";
import { Counter, Rate, Trend } from "k6/metrics";
import ws from "k6/ws";

const state = JSON.parse(open("./.state.json"));
const APP = __ENV.APP_URL || "http://localhost:3000";
const WS = __ENV.WS_URL || "ws://localhost:8000/ws";
const SOCKETS = Number(__ENV.SOCKETS || 1000);
const RATE = Number(__ENV.RATE || 50);
const HOLD = __ENV.HOLD || "5m";
const RAMP = __ENV.RAMP || "2m";
// Each socket sends on its own interval so that all of them together reach RATE messages per second.
const INTERVAL_MS = (SOCKETS / RATE) * 1000;

const delivery = new Trend("chat_delivery_ms", true);
const ackTime = new Trend("chat_ack_ms", true);
const connected = new Rate("ws_connected");
const sent = new Counter("chat_sent");
const received = new Counter("chat_received");
const refused = new Counter("chat_errors");

export const options = {
  setupTimeout: "15m",
  scenarios: {
    sockets: {
      executor: "ramping-vus",
      startVUs: 0,
      stages: [
        { duration: RAMP, target: SOCKETS },
        { duration: HOLD, target: SOCKETS },
        { duration: "30s", target: 0 },
      ],
      gracefulRampDown: "30s",
    },
  },
  thresholds: {
    // §8 non-functional target: chat delivery p95 below 300 ms.
    chat_delivery_ms: ["p(95)<300"],
    chat_ack_ms: ["p(95)<300"],
    ws_connected: ["rate>0.99"],
    chat_errors: ["count<10"],
  },
};

/**
 * Requests with redirects followed by hand and a cookie map per host. The app and Keycloak mark their cookies
 * Secure (browsers treat http://localhost as secure), which k6's cookie jar would hold back on a plain-HTTP stack.
 */
function browse(method, url, body, jars) {
  let response;
  for (let hop = 0; hop < 10; hop += 1) {
    const origin = /^https?:\/\/[^/]+/.exec(url)[0];
    const jar = (jars[origin] = jars[origin] || {});
    const cookie = Object.entries(jar)
      .map(([name, value]) => `${name}=${value}`)
      .join("; ");
    response = http.request(method, url, body, {
      headers: cookie ? { Cookie: cookie } : {},
      redirects: 0,
    });
    for (const [name, values] of Object.entries(response.cookies)) {
      if (values[0].value) jar[name] = values[0].value;
      else delete jar[name];
    }
    const location = response.headers.Location;
    if (response.status < 300 || response.status >= 400 || !location) return { response, jars };
    url = location.startsWith("/") ? origin + location : location;
    method = "GET";
    body = null;
  }
  return { response, jars };
}

/** Signs every load account in through the real browser flow (app → Keycloak form → callback). */
export function setup() {
  const sessions = [];
  for (const username of state.users) {
    const jars = {};
    const login = browse("GET", `${APP}/auth/signin?returnTo=/`, null, jars).response;
    const action = /id="kc-form-login"[^>]*action="([^"]+)"/.exec(login.body || "");
    if (!action) throw new Error(`no login form for ${username} (status ${login.status})`);
    const home = browse(
      "POST",
      action[1].replace(/&amp;/g, "&"),
      { username, password: state.password, credentialId: "" },
      jars,
    ).response;
    const csrf = /csrfToken\\?"\s*:\s*\\?"([A-Za-z0-9_-]{43})/.exec(home.body || "");
    const cookie = (jars[APP] || {}).sa_session;
    if (!csrf || !cookie) throw new Error(`sign-in failed for ${username} (status ${home.status})`);
    sessions.push({ cookie, csrf: csrf[1] });
  }
  return { sessions };
}

export default function (data) {
  const index = (__VU - 1) % data.sessions.length;
  const session = data.sessions[index];
  const channelId = state.channels[index % state.channels.length];
  const ticket = http.post(`${APP}/api/v1/ws/ticket`, null, {
    headers: {
      Cookie: `sa_session=${session.cookie}`,
      "x-csrf-token": session.csrf,
      Origin: APP,
    },
  });
  if (!check(ticket, { "ticket issued": (r) => r.status === 200 })) {
    connected.add(false);
    return;
  }
  const pending = {};
  const response = ws.connect(
    `${WS}?ticket=${encodeURIComponent(ticket.json("ticket"))}`,
    { headers: { Origin: APP } },
    (socket) => {
      socket.on("open", () => {
        connected.add(true);
        socket.send(JSON.stringify({ type: "subscribe", id: "s", data: { channel_ids: [channelId] } }));
        // A random first send spreads the sockets evenly over the interval.
        socket.setTimeout(() => {
          socket.setInterval(() => {
            const id = `${__VU}-${Date.now()}`;
            pending[id] = Date.now();
            sent.add(1);
            socket.send(
              JSON.stringify({
                type: "message.send",
                id,
                data: {
                  channel_id: channelId,
                  body: `Yük testi ${Date.now()}`,
                  client_msg_id: crypto.randomUUID(),
                },
              }),
            );
          }, INTERVAL_MS);
        }, Math.random() * INTERVAL_MS);
      });
      socket.on("message", (raw) => {
        const event = JSON.parse(raw);
        if (event.type === "message.created") {
          const at = /^Yük testi (\d+)$/.exec(event.data.body || "");
          if (at) {
            received.add(1);
            delivery.add(Date.now() - Number(at[1]));
          }
        } else if (event.type === "ack" && event.data.id in pending) {
          ackTime.add(Date.now() - pending[event.data.id]);
          delete pending[event.data.id];
        } else if (event.type === "error") {
          refused.add(1);
        }
      });
      // Sockets stay open until the scenario ramps the VU down.
      socket.setTimeout(() => socket.close(), 60 * 60 * 1000);
    },
  );
  if (response.status !== 101) connected.add(false);
}
