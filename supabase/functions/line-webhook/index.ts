// LINE Webhook — ThaiCarbide / Nong AI
// Receives LINE messages → Claude AI reply → saves to Supabase → Telegram summary

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const LINE_CHANNEL_SECRET  = Deno.env.get("LINE_CHANNEL_SECRET")      || "";
const LINE_CHANNEL_TOKEN   = Deno.env.get("LINE_CHANNEL_TOKEN")        || "";
const ANTHROPIC_API_KEY    = Deno.env.get("ANTHROPIC_API_KEY")         || "";
const TELEGRAM_BOT_TOKEN   = Deno.env.get("TELEGRAM_BOT_TOKEN")        || "";
const TELEGRAM_CHAT_ID     = Deno.env.get("TELEGRAM_CHAT_ID")          || "";
const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")              || "";
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

// ── Nong system prompt ─────────────────────────────────────────────────────

const NONG_SYSTEM = `คุณคือ Nong (น้อง) ผู้ช่วยฝ่ายขายของ ThaiCarbide.com — บริษัทรับซื้อเศษคาร์ไบด์ในประเทศไทย

ภารกิจของคุณ: ช่วยลูกค้าที่ส่งข้อความมาทาง LINE และนำทางพวกเขาไปสู่การกรอกแบบฟอร์ม

กฎเหล็ก:
- ตอบเป็นภาษาไทยเสมอ (ถ้าลูกค้าเขียนอังกฤษ ตอบไทยก็ได้แต่ให้มีภาษาอังกฤษสั้นๆ ด้วย)
- ห้ามบอกราคาที่แน่นอน — บอกว่าราคาขึ้นกับชนิดและน้ำหนัก และให้กรอกฟอร์ม
- ข้อความสั้น กระชับ เหมาะกับมือถือ ไม่เกิน 4-5 บรรทัด
- อย่าใช้ markdown หรือ ** ตัวหนา — เป็นข้อความธรรมดาเท่านั้น

ข้อมูลที่ตอบได้:
- รับซื้อ: อินเสิร์ท, ดอกสว่าน, เอ็นมิล, คาร์ไบด์ผสม ทุกชนิด
- ขั้นต่ำ: 1 กิโลกรัม ไม่มีขั้นต่ำ
- รับฟรีถึงที่: กรุงเทพฯ และ Eastern Seaboard 20 กก.ขึ้นไป (ต่ำกว่านั้นส่ง Kerry/J&T)
- จ่ายเงิน: ภายใน 48 ชั่วโมงหลังรับวัสดุ PromptPay หรือโอนธนาคาร
- ราคา: อัปเดตทุกวันตามตลาดโลก — กรอกฟอร์มเพื่อรับราคาที่แน่นอน

ลิงก์ฟอร์ม: thaicarbide.com/checkout.html

ขั้นตอนการขาย:
1. ถามว่ามีคาร์ไบด์ประเภทไหน
2. ถามน้ำหนักโดยประมาณ
3. ขอ LINE ID หรือเบอร์โทร
4. ส่งลิงก์ฟอร์มให้กรอก

ถ้าลูกค้าสนใจขายให้จบด้วย: "กรอกได้เลยครับ: thaicarbide.com/checkout.html"`;

// ── Signature verification ─────────────────────────────────────────────────

async function verifySignature(body: string, signature: string): Promise<boolean> {
  if (!LINE_CHANNEL_SECRET) return true;
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(LINE_CHANNEL_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(body));
  const expected = btoa(String.fromCharCode(...new Uint8Array(sig)));
  return expected === signature;
}

// ── Conversation history ───────────────────────────────────────────────────

interface ChatMessage { role: "user" | "assistant"; content: string; }

async function getHistory(supabase: ReturnType<typeof createClient>, userId: string): Promise<ChatMessage[]> {
  const { data } = await supabase
    .from("line_chats")
    .select("message, bot_reply, created_at")
    .eq("line_user_id", userId)
    .order("created_at", { ascending: false })
    .limit(6); // last 6 exchanges = 12 turns max

  if (!data || data.length === 0) return [];

  const msgs: ChatMessage[] = [];
  // Reverse so oldest first
  for (const row of [...data].reverse()) {
    if (row.message) msgs.push({ role: "user",      content: row.message });
    if (row.bot_reply) msgs.push({ role: "assistant", content: row.bot_reply });
  }
  return msgs;
}

// ── Claude AI ─────────────────────────────────────────────────────────────

async function askNong(history: ChatMessage[], userMessage: string): Promise<string> {
  if (!ANTHROPIC_API_KEY) return "ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาติดต่อ @280uqpab";

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-haiku-4-5-20251001",
      max_tokens: 300,
      system: NONG_SYSTEM,
      messages: [
        ...history,
        { role: "user", content: userMessage },
      ],
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    console.error("[line-webhook] Anthropic error:", JSON.stringify(data));
    return "ขออภัยครับ กรุณาลองใหม่อีกครั้ง";
  }
  return data.content?.[0]?.text || "ขออภัยครับ กรุณาลองใหม่อีกครั้ง";
}

// ── LINE helpers ───────────────────────────────────────────────────────────

async function getDisplayName(userId: string): Promise<string> {
  if (!LINE_CHANNEL_TOKEN) return userId.slice(-6);
  try {
    const res = await fetch(`https://api.line.me/v2/bot/profile/${userId}`, {
      headers: { "Authorization": `Bearer ${LINE_CHANNEL_TOKEN}` },
    });
    const d = await res.json();
    return d.displayName || userId.slice(-6);
  } catch { return userId.slice(-6); }
}

async function replyLine(replyToken: string, text: string): Promise<boolean> {
  if (!LINE_CHANNEL_TOKEN) {
    console.warn("[line-webhook] LINE_CHANNEL_TOKEN not set — cannot reply");
    return false;
  }
  const res = await fetch("https://api.line.me/v2/bot/message/reply", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${LINE_CHANNEL_TOKEN}`,
    },
    body: JSON.stringify({ replyToken, messages: [{ type: "text", text }] }),
  });
  if (!res.ok) console.error("[line-webhook] LINE reply failed:", res.status, await res.text());
  return res.ok;
}

// ── Telegram helper ────────────────────────────────────────────────────────

async function alertTelegram(user: string, question: string, reply: string) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  const text = `💬 LINE: ${user} ถาม:\n"${question.slice(0, 120)}"\n\n✅ Nong ตอบ:\n"${reply.slice(0, 200)}"`;
  await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text }),
  }).catch(() => {});
}

// ── Main handler ───────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "GET") {
    return new Response(JSON.stringify({ ok: true, service: "line-webhook-ai", model: "claude-haiku-4-5-20251001" }), {
      headers: { "Content-Type": "application/json" },
    });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const body = await req.text();
  const signature = req.headers.get("x-line-signature") || "";

  if (!(await verifySignature(body, signature))) {
    console.error("[line-webhook] Invalid signature — rejected");
    return new Response("Forbidden", { status: 403 });
  }

  let payload: { events?: Record<string, unknown>[] };
  try { payload = JSON.parse(body); }
  catch { return new Response("Bad JSON", { status: 400 }); }

  // Return 200 immediately — LINE requires fast response
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  // Process events in background
  (async () => {
    for (const event of (payload.events || [])) {
      // ── Follow event: send welcome message ────────────────────────────────
      if (event.type === "follow") {
        const source = event.source as Record<string, unknown>;
        const userId = (source?.userId as string) || "unknown";
        const replyToken = event.replyToken as string;
        const welcomeMsg = "สวัสดีครับ! 😊 ขอบคุณที่ add ThaiCarbide นะครับ\nมีเศษคาร์ไบด์อยากขายไหมครับ?\nส่งรูปมาได้เลย หรือกรอกแบบฟอร์ม:\nthaicarbide.com/checkout.html\nเราจ่ายเงินสดภายใน 48 ชม. 💰";
        await replyLine(replyToken, welcomeMsg);
        const name = await getDisplayName(userId);
        await alertTelegram(name, "[ใหม่ — add friend]", welcomeMsg);
        continue;
      }

      if (event.type !== "message") continue;

      const msg     = event.message as Record<string, unknown>;
      const source  = event.source as Record<string, unknown>;
      const userId  = (source?.userId as string) || "unknown";
      const replyToken = event.replyToken as string;
      const ts      = new Date(event.timestamp as number).toISOString();

      // Text messages only
      if (msg?.type !== "text") {
        // Image: save + alert, no AI reply
        if (msg?.type === "image") {
          const name = await getDisplayName(userId);
          await supabase.from("line_chats").insert({ line_user_id: userId, display_name: name, message: "[รูปภาพ]", created_at: ts });
          await alertTelegram(name, "[ส่งรูปภาพ]", "— (ไม่มีการตอบกลับอัตโนมัติสำหรับรูปภาพ)");
        }
        continue;
      }

      const userMessage = msg.text as string;
      const msgId = msg.id as string;

      try {
        // 1. Get display name + conversation history in parallel
        const [displayName, history] = await Promise.all([
          getDisplayName(userId),
          getHistory(supabase, userId),
        ]);

        // 2. Ask Claude
        const nongReply = await askNong(history, userMessage);

        // 3. Save to Supabase (user message + bot reply together)
        await supabase.from("line_chats").insert({
          line_user_id: userId,
          display_name: displayName,
          message: userMessage,
          bot_reply: nongReply,
          reply_token: replyToken,
          msg_id: msgId,
          created_at: ts,
        });

        // 4. Reply via LINE
        await replyLine(replyToken, nongReply);

        // 5. Telegram summary
        await alertTelegram(displayName, userMessage, nongReply);

        console.log(`[line-webhook] ${displayName}: "${userMessage.slice(0,50)}" → replied ${nongReply.length} chars`);

      } catch (e) {
        console.error("[line-webhook] Error processing message:", e);
        // Best-effort fallback reply
        await replyLine(replyToken, "ขออภัยครับ เกิดข้อผิดพลาดชั่วคราว กรุณาลองใหม่หรือ LINE: @280uqpab").catch(() => {});
      }
    }
  })();

  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
