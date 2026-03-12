// LINE Webhook — ThaiCarbide
// Receives LINE OA messages, saves to Supabase, alerts Telegram, auto-replies.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const LINE_CHANNEL_SECRET = Deno.env.get("LINE_CHANNEL_SECRET") || "";
const LINE_CHANNEL_TOKEN  = Deno.env.get("LINE_CHANNEL_TOKEN")  || "";
const TELEGRAM_BOT_TOKEN  = Deno.env.get("TELEGRAM_BOT_TOKEN")  || "";
const TELEGRAM_CHAT_ID    = Deno.env.get("TELEGRAM_CHAT_ID")    || "";
const SUPABASE_URL        = Deno.env.get("SUPABASE_URL")        || "";
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const AUTO_REPLY = `สวัสดีครับ! 😊 ThaiCarbide รับซื้อเศษคาร์ไบด์ทุกชนิด
✅ ดอกเอ็นมิล / ดอกสว่าน / อินเสิร์ท / คาร์ไบด์ผสม
✅ รับซื้อขั้นต่ำ 1 กิโลกรัม
✅ จ่ายเงินภายใน 48 ชม.

📋 กรอกแบบฟอร์มเพื่อรับราคาที่แน่นอน:
thaicarbide.com/checkout.html
หรือส่งรูปวัสดุมาได้เลยครับ 📸`;

// ── Signature verification ─────────────────────────────────────────────────

async function verifySignature(body: string, signature: string): Promise<boolean> {
  if (!LINE_CHANNEL_SECRET) return true; // skip if secret not set
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(LINE_CHANNEL_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(body));
  const expected = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return expected === signature;
}

// ── LINE helpers ───────────────────────────────────────────────────────────

async function getDisplayName(userId: string): Promise<string> {
  if (!LINE_CHANNEL_TOKEN) return userId;
  try {
    const res = await fetch(`https://api.line.me/v2/bot/profile/${userId}`, {
      headers: { "Authorization": `Bearer ${LINE_CHANNEL_TOKEN}` },
    });
    const d = await res.json();
    return d.displayName || userId;
  } catch { return userId; }
}

async function replyLine(replyToken: string, text: string) {
  if (!LINE_CHANNEL_TOKEN) return;
  await fetch("https://api.line.me/v2/bot/message/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${LINE_CHANNEL_TOKEN}`,
    },
    body: JSON.stringify({ replyToken, messages: [{ type: "text", text }] }),
  });
}

// ── Telegram helper ────────────────────────────────────────────────────────

async function alertTelegram(text: string) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text }),
  });
}

// ── Main ──────────────────────────────────────────────────────────────────

serve(async (req) => {
  // LINE health check
  if (req.method === "GET") {
    return new Response(JSON.stringify({ ok: true, service: "line-webhook" }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const body = await req.text();
  const signature = req.headers.get("x-line-signature") || "";

  if (!(await verifySignature(body, signature))) {
    console.error("[line-webhook] Invalid signature");
    return new Response("Forbidden", { status: 403 });
  }

  let payload: { events?: Record<string, unknown>[] };
  try { payload = JSON.parse(body); }
  catch { return new Response("Bad JSON", { status: 400 }); }

  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  for (const event of (payload.events || [])) {
    if (event.type !== "message") continue;
    const msg = event.message as Record<string, unknown>;
    const source = event.source as Record<string, unknown>;
    const userId = (source?.userId as string) || "unknown";
    const replyToken = event.replyToken as string;
    const ts = new Date(event.timestamp as number).toISOString();

    // Text messages
    if (msg?.type === "text") {
      const text = msg.text as string;
      const displayName = await getDisplayName(userId);

      // 1. Save to Supabase
      const { error } = await supabase.from("line_chats").insert({
        line_user_id: userId,
        display_name: displayName,
        message: text,
        reply_token: replyToken,
        created_at: ts,
      });
      if (error) console.error("[line-webhook] DB insert error:", error.message);

      // 2. Auto-reply
      await replyLine(replyToken, AUTO_REPLY);

      // 3. Telegram alert
      await alertTelegram(
        `💬 LINE จาก ${displayName}:\n"${text}"\n→ ตอบที่ manager.line.biz`
      );

      console.log(`[line-webhook] Message from ${displayName}: ${text.slice(0, 60)}`);
    }

    // Image messages — alert only, no auto-reply text
    if (msg?.type === "image") {
      const displayName = await getDisplayName(userId);
      await supabase.from("line_chats").insert({
        line_user_id: userId,
        display_name: displayName,
        message: "[รูปภาพ]",
        reply_token: replyToken,
        created_at: ts,
      });
      await alertTelegram(
        `📸 LINE รูปภาพจาก ${displayName}\n→ ดูที่ manager.line.biz`
      );
    }
  }

  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
