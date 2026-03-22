// Facebook Messenger Webhook — ThaiCarbide / Nong AI
// Receives FB Messenger messages → Claude AI reply → saves to Supabase → Telegram summary
// Same logic & welcome message as line-webhook

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const FB_PAGE_ACCESS_TOKEN = Deno.env.get("FB_PAGE_ACCESS_TOKEN") || "";
const FB_VERIFY_TOKEN      = Deno.env.get("FB_VERIFY_TOKEN")      || "";
const FB_APP_SECRET        = Deno.env.get("FB_APP_SECRET")        || "";
const ANTHROPIC_API_KEY    = Deno.env.get("ANTHROPIC_API_KEY")    || "";
const TELEGRAM_BOT_TOKEN   = Deno.env.get("TELEGRAM_BOT_TOKEN")   || "";
const TELEGRAM_CHAT_ID     = Deno.env.get("TELEGRAM_CHAT_ID")     || "";
const SUPABASE_URL         = Deno.env.get("SUPABASE_URL")         || "";
const SUPABASE_SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

// ── Welcome message (identical to LINE) ───────────────────────────────────

const WELCOME_MSG = "สวัสดีครับ! ยินดีต้อนรับสู่ ThaiCarbide 🏆\nผู้รับซื้อคาร์ไบด์อันดับ 1 ในประเทศไทยครับ\n\n💰 ต้องการทราบราคา? กรอกข้อมูลได้เลยครับ:\n👉 https://thaicarbide.com/sell.html\n→ เห็นราคาทันที อัปเดตทุกวันตามตลาดโลกครับ\n\n📋 ขั้นตอนง่ายๆ:\n1️⃣ กรอกข้อมูลในลิงก์ → เห็นราคาทันที\n2️⃣ เราจัดส่งรถไปรับถึงที่ฟรีครับ\n3️⃣ ชั่งน้ำหนัก ตรวจสอบ → โอนเงินภายใน 48 ชั่วโมง 💸\n\n📸 มีรูปสินค้า? ส่งมาได้เลยครับ เราประเมินให้ฟรีครับ";

const IMAGE_REPLY = "ขอบคุณสำหรับรูปครับ! 📸\nเราประเมินให้ฟรีเลย — ดูเหมือนคาร์ไบด์ครับ ราคาดีมากเลย\n\nกรอกข้อมูลเพื่อรับราคาที่แน่นอนได้เลยครับ:\n👉 https://thaicarbide.com/sell.html";

// ── Nong system prompt (same rules as line-webhook) ────────────────────────

const NONG_SYSTEM = `คุณคือ Nong (น้อง) ผู้ช่วยฝ่ายขายของ ThaiCarbide.com — บริษัทรับซื้อเศษคาร์ไบด์อันดับ 1 ในประเทศไทย

ภารกิจของคุณ: ช่วยลูกค้าที่ส่งข้อความมาทาง Facebook Messenger และนำทางพวกเขาไปสู่การกรอกแบบฟอร์ม

กฎเหล็ก — ห้ามละเมิดเด็ดขาด:
- ตอบเป็นภาษาไทยเสมอ (ถ้าลูกค้าเขียนอังกฤษ ตอบไทยก็ได้แต่ให้มีภาษาอังกฤษสั้นๆ ด้วย)
- ห้ามบอกราคาที่แน่นอนในแชท — ให้กรอกฟอร์มเพื่อเห็นราคาทันที
- ข้อความสั้น กระชับ เหมาะกับมือถือ ไม่เกิน 4-5 บรรทัด
- อย่าใช้ markdown หรือ ** ตัวหนา — เป็นข้อความธรรมดาเท่านั้น
- ห้ามพูดว่า "เราจะติดต่อกลับ" / "รอเราโทรหา" / "ทีมงานจะติดต่อภายใน X ชั่วโมง" — เด็ดขาด
- ระบบทำงานอัตโนมัติทั้งหมดจนกว่าลูกค้าจะกรอกฟอร์มเสร็จ
- หลังจากฟอร์มสมบูรณ์ → เจ้าของจะติดต่อลูกค้าโดยตรง

กฎพิเศษ — ผู้ซื้อ vs ผู้ขาย:
- ถ้าลูกค้าพูดว่า "ซื้อ" / "จะซื้อ" / "ต้องการซื้อ" / "หาซื้อ" / "อยากซื้อ" หมายความว่าเขาต้องการซื้อสินค้าจากเรา
- เราไม่ได้ขายสินค้า — เรารับซื้อเศษคาร์ไบด์เท่านั้น
- ตอบว่า: "ขออภัยครับ เราเป็นผู้รับซื้อเท่านั้น ไม่ได้จำหน่ายครับ 🙏"
- ถ้าลูกค้าพูดว่า "ขาย" / "อยากขาย" / "มีของขาย" — ให้ดำเนินการตามปกติ

กฎบทสนทนา:
- อ่านประวัติการสนทนา 3 ข้อความล่าสุดก่อนตอบเสมอ
- อย่าถามคำถามเดิมซ้ำในบทสนทนาเดียวกัน
- ตรวจสอบว่าได้ถามแล้วหรือยัง: ประเภท? น้ำหนัก? ข้อมูลติดต่อ? — ข้ามสิ่งที่ตอบแล้ว

การตอบเรื่องราคา:
- ถ้าลูกค้าถามราคา → "ราคาอัปเดตทุกวันตามตลาดโลกครับ กรอกข้อมูลเพื่อเห็นราคาวันนี้ได้เลย: https://thaicarbide.com/sell.html"
- ห้ามบอกตัวเลขราคาในแชท

ข้อมูลที่ตอบได้:
- รับซื้อ: อินเสิร์ท, ดอกสว่าน, เอ็นมิล, คาร์ไบด์ผสม ทุกชนิด
- ขั้นต่ำ: 1 กิโลกรัม ไม่มีขั้นต่ำ
- รับฟรีถึงที่: กรุงเทพฯ และ Eastern Seaboard 20 กก.ขึ้นไป (ต่ำกว่านั้นส่ง Kerry/J&T)
- จ่ายเงิน: ภายใน 48 ชั่วโมงหลังรับวัสดุ PromptPay หรือโอนธนาคาร

ลิงก์ฟอร์ม: https://thaicarbide.com/sell.html

ปิดด้วย: "กรอกได้เลยครับ เห็นราคาทันที: https://thaicarbide.com/sell.html"`;

// ── Signature verification ─────────────────────────────────────────────────

async function verifySignature(body: string, signature: string): Promise<boolean> {
  if (!FB_APP_SECRET) return true; // skip in dev if not set
  const sigPart = signature.replace("sha256=", "");
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(FB_APP_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(body));
  const expected = Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, "0")).join("");
  return expected === sigPart;
}

// ── Conversation history ───────────────────────────────────────────────────

interface ChatMessage { role: "user" | "assistant"; content: string; }

async function getHistory(supabase: ReturnType<typeof createClient>, userId: string): Promise<ChatMessage[]> {
  const { data } = await supabase
    .from("fb_chats")
    .select("message, bot_reply, created_at")
    .eq("fb_user_id", userId)
    .order("created_at", { ascending: false })
    .limit(6);

  if (!data || data.length === 0) return [];

  const msgs: ChatMessage[] = [];
  for (const row of [...data].reverse()) {
    if (row.message)   msgs.push({ role: "user",      content: row.message });
    if (row.bot_reply) msgs.push({ role: "assistant", content: row.bot_reply });
  }
  return msgs;
}

// ── Is first contact? ──────────────────────────────────────────────────────

async function isFirstContact(supabase: ReturnType<typeof createClient>, userId: string): Promise<boolean> {
  const { count } = await supabase
    .from("fb_chats")
    .select("id", { count: "exact", head: true })
    .eq("fb_user_id", userId);
  return (count ?? 0) === 0;
}

// ── Claude AI ─────────────────────────────────────────────────────────────

async function askNong(history: ChatMessage[], userMessage: string): Promise<string> {
  if (!ANTHROPIC_API_KEY) return "ขออภัยครับ ระบบขัดข้องชั่วคราว กรุณาติดต่อผ่าน LINE: @280uqpab";

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
      messages: [...history, { role: "user", content: userMessage }],
    }),
  });

  const data = await res.json();
  if (!res.ok) {
    console.error("[fb-webhook] Anthropic error:", JSON.stringify(data));
    return "ขออภัยครับ กรุณาลองใหม่อีกครั้ง";
  }
  return data.content?.[0]?.text || "ขออภัยครับ กรุณาลองใหม่อีกครั้ง";
}

// ── FB Send API ────────────────────────────────────────────────────────────

async function sendFbMessage(recipientId: string, text: string): Promise<void> {
  if (!FB_PAGE_ACCESS_TOKEN) {
    console.warn("[fb-webhook] FB_PAGE_ACCESS_TOKEN not set — cannot reply");
    return;
  }
  const res = await fetch(`https://graph.facebook.com/v19.0/me/messages?access_token=${FB_PAGE_ACCESS_TOKEN}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      recipient: { id: recipientId },
      message: { text },
    }),
  });
  if (!res.ok) console.error("[fb-webhook] FB send failed:", res.status, await res.text());
}

// ── Telegram helper ────────────────────────────────────────────────────────

async function alertTelegram(user: string, question: string, reply: string) {
  if (!TELEGRAM_BOT_TOKEN || !TELEGRAM_CHAT_ID) return;
  const text = `💬 FB Messenger: ${user}\n"${question.slice(0, 120)}"\n\n✅ Nong ตอบ:\n"${reply.slice(0, 200)}"`;
  await fetch(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: TELEGRAM_CHAT_ID, text }),
  }).catch(() => {});
}

// ── Main handler ───────────────────────────────────────────────────────────

serve(async (req) => {
  // Webhook verification (FB requires GET with hub params)
  if (req.method === "GET") {
    const url = new URL(req.url);
    const mode      = url.searchParams.get("hub.mode");
    const token     = url.searchParams.get("hub.verify_token");
    const challenge = url.searchParams.get("hub.challenge");

    if (mode === "subscribe" && token === FB_VERIFY_TOKEN) {
      console.log("[fb-webhook] Webhook verified");
      return new Response(challenge, { status: 200 });
    }
    return new Response("Forbidden", { status: 403 });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const body = await req.text();
  const signature = req.headers.get("x-hub-signature-256") || "";

  if (!(await verifySignature(body, signature))) {
    console.error("[fb-webhook] Invalid signature — rejected");
    return new Response("Forbidden", { status: 403 });
  }

  let payload: Record<string, unknown>;
  try { payload = JSON.parse(body); }
  catch { return new Response("Bad JSON", { status: 400 }); }

  // Return 200 immediately — FB requires fast response
  const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);

  (async () => {
    if (payload.object !== "page") return;

    for (const entry of (payload.entry as Record<string, unknown>[] || [])) {
      for (const event of (entry.messaging as Record<string, unknown>[] || [])) {
        const senderId = (event.sender as Record<string, unknown>)?.id as string;
        if (!senderId) continue;

        const ts = new Date().toISOString();

        // ── Image/attachment ───────────────────────────────────────────────
        const msg = event.message as Record<string, unknown> | undefined;
        if (msg?.attachments) {
          await supabase.from("fb_chats").insert({
            fb_user_id: senderId,
            message: "[รูปภาพ/ไฟล์]",
            bot_reply: IMAGE_REPLY,
            created_at: ts,
          });
          await sendFbMessage(senderId, IMAGE_REPLY);
          await alertTelegram(senderId, "[ส่งรูปภาพ]", IMAGE_REPLY);
          continue;
        }

        // ── Text message ───────────────────────────────────────────────────
        const text = msg?.text as string | undefined;
        if (!text) continue;

        const msgId = msg?.mid as string;

        // Dedup
        const { data: existing } = await supabase
          .from("fb_chats")
          .select("id")
          .eq("msg_id", msgId)
          .maybeSingle();
        if (existing) continue;

        try {
          // First contact → send welcome, then process message normally
          const firstContact = await isFirstContact(supabase, senderId);

          if (firstContact) {
            await sendFbMessage(senderId, WELCOME_MSG);
            await alertTelegram(senderId, "[ใหม่ — first message]", WELCOME_MSG);
          }

          const history = await getHistory(supabase, senderId);
          const nongReply = await askNong(history, text);

          await supabase.from("fb_chats").insert({
            fb_user_id: senderId,
            message: text,
            bot_reply: nongReply,
            msg_id: msgId,
            created_at: ts,
          });

          await sendFbMessage(senderId, nongReply);
          await alertTelegram(senderId, text, nongReply);

          console.log(`[fb-webhook] ${senderId}: "${text.slice(0, 50)}" → replied ${nongReply.length} chars`);

        } catch (e) {
          console.error("[fb-webhook] Error processing message:", e);
          await sendFbMessage(senderId, "ขออภัยครับ เกิดข้อผิดพลาดชั่วคราว กรุณาลองใหม่ครับ").catch(() => {});
        }
      }
    }
  })();

  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
