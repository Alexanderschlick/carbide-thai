import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, authorization",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: CORS });
  }

  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405, headers: CORS });
  }

  try {
    const { messages, lang } = await req.json();

    const ANTHROPIC_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!ANTHROPIC_KEY) {
      return new Response(JSON.stringify({ error: "API key not configured" }), {
        status: 500, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }

    const langInstruction = lang === "en"
      ? "Always respond in English, regardless of what language the user writes in."
      : "Always respond in Thai, regardless of what language the user writes in.";

    const SYSTEM_PROMPT = `You are a helpful assistant for ThaiCarbide (thaicarbide.com), a carbide scrap buying company in Bangkok, Thailand. ${langInstruction}

Key info: We buy carbide inserts up to ฿2,493/kg, drills & mills up to ฿2,493/kg, mixed carbide up to ฿1,413/kg. Price tiers: standard (1kg+), 100kg+, 350kg+. Free pickup Bangkok & Eastern Seaboard for 20kg+. Payment within 48h via PromptPay/Bank Transfer.

SELLING: Always guide customers to sell via thaicarbide.com/checkout.html — this is the main sales channel. When a customer asks about selling or prices, explain the relevant price, then direct them to fill out the form at thaicarbide.com/checkout.html to get a confirmed price within 2 hours. Example: "กรอกแบบฟอร์มที่ thaicarbide.com/checkout.html แล้วเราจะยืนยันราคาภายใน 2 ชั่วโมง" or in English: "Fill out the form at thaicarbide.com/checkout.html and we'll confirm your price within 2 hours."

LINE: @280uqpab is for support questions only (tracking, payment issues, general questions). Never suggest LINE as a way to sell or submit an order.

IMPORTANT: We do NOT accept walk-ins. Customers must either ship via Kerry/Flash courier, or we arrange pickup. The shipping address is only shown after order confirmation — do not share it in chat. Do not use markdown formatting like bold or italic. Write plain text only, no asterisks.`;

    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 512,
        system: SYSTEM_PROMPT,
        messages,
      }),
    });

    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: res.status,
      headers: { ...CORS, "Content-Type": "application/json" },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500, headers: { ...CORS, "Content-Type": "application/json" },
    });
  }
});
