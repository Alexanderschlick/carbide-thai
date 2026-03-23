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

const NONG_SYSTEM = `คุณคือ Nong (น้อง) ผู้ช่วยฝ่ายขายของ ThaiCarbide.com — บริษัทรับซื้อเศษคาร์ไบด์อันดับ 1 ในประเทศไทย

ภารกิจของคุณ: ช่วยลูกค้าที่ส่งข้อความมาทาง LINE และนำทางพวกเขาไปสู่การกรอกแบบฟอร์ม

กฎเหล็ก — ห้ามละเมิดเด็ดขาด:
- ตอบเป็นภาษาไทยเสมอ (ถ้าลูกค้าเขียนอังกฤษ ตอบไทยก็ได้แต่ให้มีภาษาอังกฤษสั้นๆ ด้วย)
- ห้ามบอกราคาที่แน่นอนในแชท — ให้กรอกฟอร์มเพื่อเห็นราคาทันที
- ข้อความสั้น กระชับ เหมาะกับมือถือ ไม่เกิน 4-5 บรรทัด
- อย่าใช้ markdown หรือ ** ตัวหนา — เป็นข้อความธรรมดาเท่านั้น
- ห้ามพูดว่า "เราจะติดต่อกลับ" / "รอเราโทรหา" / "ทีมงานจะติดต่อภายใน X ชั่วโมง" — เด็ดขาด
- ระบบทำงานอัตโนมัติทั้งหมดจนกว่าลูกค้าจะกรอกฟอร์มเสร็จ
- หลังจากฟอร์มสมบูรณ์ → เจ้าของจะติดต่อลูกค้าโดยตรง (ลูกค้าไม่ต้องรอเราโทร)

กฎพิเศษ — ผู้ซื้อ vs ผู้ขาย:
- ถ้าลูกค้าพูดว่า "ซื้อ" / "จะซื้อ" / "ต้องการซื้อ" / "หาซื้อ" / "อยากซื้อ" (ภาษาไทย) หมายความว่าเขาต้องการซื้อสินค้าจากเรา
  → ตอบว่า: "ขออภัยครับ เราเป็นผู้รับซื้อเท่านั้น ไม่ได้จำหน่ายครับ 🙏"
  → อย่าส่งลิงก์ฟอร์มให้ผู้ที่ต้องการซื้อสินค้า
- ถ้าลูกค้าเขียนภาษาอังกฤษว่า "I want to buy" / "buying" / "interested in purchasing" / "tons" / "supply" / "prices" (ในบริบทการซื้อ)
  → นี่คือลูกค้า B2B ที่ต้องการซื้อจากเรา — ห้ามพูดว่า "เรารับซื้ออย่างเดียว"
  → ตอบว่า: "Please send your requirements to thaicarbide@gmail.com — our team will respond within 24 hours."
- ถ้าลูกค้าพูดว่า "ขาย" / "อยากขาย" / "มีของขาย" / "sell" / "selling" — ให้ดำเนินการตามปกติ

กฎบทสนทนา:
- อ่านประวัติการสนทนา 3 ข้อความล่าสุดก่อนตอบเสมอ
- อย่าถามคำถามเดิมซ้ำในบทสนทนาเดียวกัน
  เช่น ถ้าถาม "มีคาร์ไบด์ประเภทไหน" แล้ว อย่าถามอีก — ใช้คำตอบที่ได้รับแล้ว
- ตรวจสอบว่าได้ถามแล้วหรือยัง: ประเภท? น้ำหนัก? ข้อมูลติดต่อ? — ข้ามสิ่งที่ตอบแล้ว

การตอบเรื่องราคา:
- ถ้าลูกค้าถามราคา → ตอบว่า "ราคาอัปเดตทุกวันตามตลาดโลกครับ กรอกข้อมูลเพื่อเห็นราคาวันนี้ได้เลย: https://thaicarbide.com/sell.html"
- ห้ามบอกตัวเลขราคาในแชท เพราะราคาเปลี่ยนทุกวัน

การตอบเรื่องรูปภาพ:
- ถ้าลูกค้าส่งรูป → ประเมินว่าน่าจะเป็นคาร์ไบด์ประเภทไหน บอกโดยประมาณ แล้วชวนกรอกฟอร์ม
- ตัวอย่าง: "จากรูปนี้น่าจะเป็นอินเสิร์ทครับ ราคาดีมากเลย กรอกข้อมูลได้เลย: https://thaicarbide.com/sell.html"

ข้อมูลที่ตอบได้:
- รับซื้อ: อินเสิร์ท, ดอกสว่าน, เอ็นมิล, คาร์ไบด์ผสม ทุกชนิด
- ขั้นต่ำ: 1 กิโลกรัม ไม่มีขั้นต่ำ
- รับฟรีถึงที่: กรุงเทพฯ และ Eastern Seaboard 20 กก.ขึ้นไป (ต่ำกว่านั้นส่ง Kerry/J&T)
- จ่ายเงิน: ภายใน 48 ชั่วโมงหลังรับวัสดุ PromptPay หรือโอนธนาคาร
- ราคา: อัปเดตทุกวันตามตลาดโลก — กรอกฟอร์มเพื่อเห็นราคาวันนี้ทันที

ลิงก์ฟอร์ม: https://thaicarbide.com/sell.html

ขั้นตอนการขาย (เฉพาะผู้ที่ต้องการขายให้เรา):
1. ถามว่ามีคาร์ไบด์ประเภทไหน (ถ้ายังไม่รู้)
2. ถามน้ำหนักโดยประมาณ (ถ้ายังไม่รู้)
3. ส่งลิงก์ฟอร์มให้กรอก — ลูกค้าเห็นราคาทันทีในฟอร์ม
4. หลังจากกรอกฟอร์มสมบูรณ์ ทีมงานจะติดต่อเพื่อนัดรับสินค้า

ปิดด้วย: "กรอกได้เลยครับ เห็นราคาทันที: https://thaicarbide.com/sell.html"`;


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
        const welcomeMsg = "สวัสดีครับ! ยินดีต้อนรับสู่ ThaiCarbide 🏆\nผู้รับซื้อคาร์ไบด์อันดับ 1 ในประเทศไทยครับ\n\n💰 ต้องการทราบราคา? กรอกข้อมูลได้เลยครับ:\n👉 https://thaicarbide.com/sell.html\n→ เห็นราคาทันที อัปเดตทุกวันตามตลาดโลกครับ\n\n📋 ขั้นตอนง่ายๆ:\n1️⃣ กรอกข้อมูลในลิงก์ → เห็นราคาทันที\n2️⃣ เราจัดส่งรถไปรับถึงที่ฟรีครับ\n3️⃣ ชั่งน้ำหนัก ตรวจสอบ → โอนเงินภายใน 48 ชั่วโมง 💸\n\n📸 มีรูปสินค้า? ส่งมาได้เลยครับ เราประเมินให้ฟรีครับ";
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
        // Image: save + alert + auto-reply directing to form
        if (msg?.type === "image") {
          const name = await getDisplayName(userId);
          const imageReply = "ขอบคุณสำหรับรูปครับ! 📸\nเราประเมินให้ฟรีเลย — ดูเหมือนคาร์ไบด์ครับ ราคาดีมากเลย\n\nกรอกข้อมูลเพื่อรับราคาที่แน่นอนได้เลยครับ:\n👉 https://thaicarbide.com/sell.html";
          await supabase.from("line_chats").insert({ line_user_id: userId, display_name: name, message: "[รูปภาพ]", bot_reply: imageReply, created_at: ts });
          await replyLine(replyToken, imageReply);
          await alertTelegram(name, "[ส่งรูปภาพ]", imageReply);
        }
        continue;
      }

      const userMessage = msg.text as string;
      const msgId = msg.id as string;

      // Dedup: skip if we already processed this message ID
      const { data: existing } = await supabase
        .from("line_chats")
        .select("id")
        .eq("msg_id", msgId)
        .maybeSingle();
      if (existing) {
        console.log(`[line-webhook] Duplicate msg_id ${msgId} — skipping`);
        continue;
      }

      let replied = false;
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
        replied = true;

        // 5. Telegram summary
        await alertTelegram(displayName, userMessage, nongReply);

        console.log(`[line-webhook] ${displayName}: "${userMessage.slice(0,50)}" → replied ${nongReply.length} chars`);

      } catch (e) {
        console.error("[line-webhook] Error processing message:", e);
        // Best-effort fallback reply — only if we haven't already replied
        if (!replied) {
          await replyLine(replyToken, "ขออภัยครับ เกิดข้อผิดพลาดชั่วคราว กรุณาลองใหม่หรือ LINE: @280uqpab").catch(() => {});
        }
      }
    }
  })();

  return new Response(JSON.stringify({ ok: true }), {
    headers: { "Content-Type": "application/json" },
  });
});
