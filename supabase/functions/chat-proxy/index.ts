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
    const { messages } = await req.json();

    const ANTHROPIC_KEY = Deno.env.get("ANTHROPIC_API_KEY");
    if (!ANTHROPIC_KEY) {
      return new Response(JSON.stringify({ error: "API key not configured" }), {
        status: 500, headers: { ...CORS, "Content-Type": "application/json" },
      });
    }

    const SYSTEM_PROMPT = `You are a helpful assistant for ThaiCarbide (thaicarbide.com), a carbide scrap buying company in Bangkok, Thailand. Always respond in Thai. Key info: We buy carbide inserts up to ฿2,493/kg, drills & mills up to ฿2,493/kg, mixed carbide up to ฿1,413/kg. Price tiers: standard (1kg+), 100kg+, 350kg+. Free pickup Bangkok & Eastern Seaboard for 20kg+. Payment within 48h via PromptPay/Bank Transfer. Contact via LINE: alex.schlick. IMPORTANT: We do NOT accept walk-ins. Customers must either ship via Kerry/Flash courier, or we arrange pickup. The shipping address is only for courier shipments and is shown after order confirmation — do not share it in chat.`;

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
