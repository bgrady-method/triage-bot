// Cloudflare Worker: Slack Events API → Claude routine /fire bridge.
//
// Flow:
//   1. Slack POSTs an event to this Worker's URL.
//   2. We verify the X-Slack-Signature HMAC against SLACK_SIGNING_SECRET.
//   3. We respond to URL verification challenges.
//   4. For real message events on allowlisted channels, we reshape the payload
//      and forward it to the routine's /fire endpoint.
//   5. In observation mode (PHASE === "0"), we instead post the reshape to
//      DEBUG_CHANNEL_ID via Slack chat.postMessage. No routine fired.
//
// Required secrets (wrangler secret put):
//   SLACK_SIGNING_SECRET     - Slack app's signing secret (HMAC verification)
//   SLACK_BOT_TOKEN          - xoxb-... for chat.postMessage in debug mode
//   ROUTINE_FIRE_URL         - Anthropic routine /fire endpoint URL
//   ROUTINE_FIRE_TOKEN       - Bearer token for /fire
//   ALLOWED_CHANNELS         - comma-separated Slack channel IDs (the 4 alert channels)
//   DEBUG_CHANNEL_ID         - #triage-bot-debug channel ID (Phase 0 only)
//   PHASE                    - "0" for observation, "1" for live (forwards to routine)

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("triage-bot slack receiver", { status: 200 });
    }

    const rawBody = await request.text();

    // 1. Signature verification (Slack docs: https://api.slack.com/authentication/verifying-requests-from-slack)
    const ts = request.headers.get("X-Slack-Request-Timestamp");
    const sig = request.headers.get("X-Slack-Signature");
    if (!ts || !sig) return new Response("missing signature headers", { status: 401 });

    // Reject replays older than 5 minutes
    if (Math.abs(Date.now() / 1000 - Number(ts)) > 60 * 5) {
      return new Response("stale request", { status: 401 });
    }

    const expected = await sign(`v0:${ts}:${rawBody}`, env.SLACK_SIGNING_SECRET);
    if (!safeEqual(sig, `v0=${expected}`)) {
      return new Response("bad signature", { status: 401 });
    }

    let body;
    try { body = JSON.parse(rawBody); } catch { return new Response("bad json", { status: 400 }); }

    // 2. URL verification handshake
    if (body.type === "url_verification") {
      return new Response(JSON.stringify({ challenge: body.challenge }), {
        headers: { "content-type": "application/json" },
      });
    }

    // 3. Real events
    if (body.type !== "event_callback" || !body.event) return new Response("ok");

    const ev = body.event;
    if (ev.type !== "message" || ev.subtype === "message_changed" || ev.subtype === "message_deleted") {
      return new Response("ok");
    }
    // Skip the bot's own messages to prevent loops
    if (ev.bot_id || ev.subtype === "bot_message") return new Response("ok");

    const allowed = (env.ALLOWED_CHANNELS || "").split(",").map(s => s.trim()).filter(Boolean);
    if (!allowed.includes(ev.channel)) return new Response("ok");

    const payload = reshape(body, ev);

    // Slack expects 200 within 3s; do the forwarding async so we don't block.
    const phase = env.PHASE || "0";
    if (phase === "0") {
      // Observation: post to debug channel, don't fire routine
      ctxAfter(postToSlack(env, env.DEBUG_CHANNEL_ID, formatDebug(payload)));
    } else {
      ctxAfter(fireRoutine(env, payload));
    }

    return new Response("ok");
  },
};

function reshape(body, ev) {
  return {
    alert_id: `${ev.channel}:${ev.thread_ts || ev.ts}`,
    team_id: body.team_id,
    channel_id: ev.channel,
    channel_name: null, // resolved server-side if needed; left null here
    ts: ev.ts,
    thread_ts: ev.thread_ts || null,
    user: ev.user || null,
    text: ev.text || "",
    blocks: ev.blocks || null,
    attachments: ev.attachments || null,
    files: (ev.files || []).map(f => ({ name: f.name, mimetype: f.mimetype, url: f.url_private })),
    permalink: null, // routine can resolve via Slack API if needed
    received_at: new Date().toISOString(),
  };
}

function formatDebug(p) {
  const text = (p.text || "").slice(0, 500);
  return `*[debug] received alert*\n` +
    `channel: \`${p.channel_id}\`  ts: \`${p.ts}\`\n` +
    `text:\n\`\`\`\n${text}\n\`\`\`\n` +
    `attachments: ${(p.attachments || []).length}  blocks: ${(p.blocks || []).length}  files: ${p.files.length}`;
}

async function postToSlack(env, channel, text) {
  const r = await fetch("https://slack.com/api/chat.postMessage", {
    method: "POST",
    headers: {
      "content-type": "application/json; charset=utf-8",
      authorization: `Bearer ${env.SLACK_BOT_TOKEN}`,
    },
    body: JSON.stringify({ channel, text, mrkdwn: true }),
  });
  if (!r.ok) console.error("slack post failed", r.status, await r.text());
}

async function fireRoutine(env, payload) {
  // Anthropic routines accept a `text` body. We send the alert payload as JSON-in-text
  // so the routine prompt can parse it back.
  const r = await fetch(env.ROUTINE_FIRE_URL, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${env.ROUTINE_FIRE_TOKEN}`,
    },
    body: JSON.stringify({ text: JSON.stringify(payload) }),
  });
  if (!r.ok) console.error("routine fire failed", r.status, await r.text());
}

function ctxAfter(promise) {
  // Cloudflare's waitUntil-equivalent — let response return immediately.
  // (When invoked from inside fetch, the runtime keeps the worker alive for outstanding promises.)
  promise.catch(err => console.error("background task failed", err));
}

async function sign(message, secret) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
  return [...new Uint8Array(sigBuf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
