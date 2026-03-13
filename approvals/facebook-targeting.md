# Facebook Targeting Strategy — ThaiCarbide
**Status:** Draft for approval
**Created:** 2026-03-13

---

## Core Audience

**Who we want:** Factory workers and CNC machine operators who handle carbide tooling day-to-day — the people who actually see the scrap accumulate, not the people who sign contracts.

**Who we DON'T want:** Procurement managers, plant managers, CEOs, business owners (they don't feel the pain of scrap sitting idle).

---

## Audience A — CNC Operators (Primary)

| Setting | Value |
|---------|-------|
| Age | 25–45 |
| Gender | Male (skew male, but don't exclude female) |
| Language | Thai |
| Location | Thailand — prioritize Eastern Seaboard, Bangkok, Ayutthaya industrial zones |
| Job Titles | CNC operator, machine operator, ช่างซีเอ็นซี, ช่างกลึง, ช่างเจาะ |
| Interests | CNC machining, metalworking, manufacturing, Fanuc, Mazak, DMG Mori, Sandvik Coromant, ISCAR, Kennametal |
| Behaviors | Small business owners (proxy for hands-on factory workers), Works in manufacturing |

**Exclude:** Job titles containing "manager", "director", "CEO", "president", "supervisor", "หัวหน้า", "ผู้จัดการ"

---

## Audience B — Factory Floor (Lookalike Base)

Build a lookalike from:
1. LINE OA contact list (export to Custom Audience)
2. Website visitors — thaicarbide.com (Facebook Pixel, 30-day window)
3. Form submitters — checkout.html conversions

**Lookalike:** 1–2% similarity, Thailand only

---

## Audience C — Retargeting

**Who:** Anyone who visited thaicarbide.com but did NOT submit checkout.html

**Ad copy:** Reminder — เศษที่ยังอยู่ รอให้ช่วยขายให้นะ 😊
**CTA:** กรอกฟอร์มเลย (link to checkout.html)
**Duration:** 14-day window
**Budget:** ฿50/day (small, high intent)

---

## Geographic Priority

| Zone | Priority | Why |
|------|----------|-----|
| Eastern Seaboard (Chonburi, Rayong, Chachoengsao) | ⭐⭐⭐ Highest | Highest factory density, auto parts, electronics |
| Bangkok + Suburbs (Lat Krabang, Bang Na, Samut Prakan) | ⭐⭐⭐ High | Large CNC shops, diverse industry |
| Ayutthaya / Saraburi | ⭐⭐ Medium | Auto parts hub |
| Chiang Mai / Lamphun | ⭐ Lower | Precision machining but smaller volume |

Use radius targeting: 15km around major industrial estates.

---

## Placement

- **Facebook Feed** (desktop + mobile) — primary
- **Facebook Reels** — test with Video v2 only
- **Messenger** — enable for direct LINE handoff
- **Instagram** — exclude initially (wrong demographic for factory workers)
- **Audience Network** — exclude (low quality for B2B)

---

## Pixel Setup (Required Before Launch)

1. Facebook Pixel already in `index.html` (G-RNXH6EX220 is GA4 — need separate FB Pixel ID)
2. Add Pixel base code to: index.html, checkout.html, thank-you.html
3. Set up conversion event on thank-you.html: `fbq('track', 'Lead')`
4. Set up LINE message click as: `fbq('track', 'Contact')`

---

## Campaign Structure

```
Campaign: ThaiCarbide — Scrap Buyers Thailand
  └── Ad Set A: CNC Operators — Eastern Seaboard
        └── Ad 1 (Pain Point)
        └── Ad 2 (Price Hook)
  └── Ad Set B: Factory Workers — Bangkok
        └── Ad 1 (Pain Point)
        └── Ad 3 (Social Proof)
  └── Ad Set C: Retargeting — Site Visitors
        └── Retargeting ad
```

**Optimization:** Optimize for "Messages" (LINE OA) in phase 1, switch to "Leads" once pixel has 50+ conversions.

---

## Notes
- LINE OA integration is key: ad CTA → LINE → Nong handles 24/7
- Keep copy casual (ภาษาพูด) — operators respond to peer-to-peer tone, not corporate language
- Test ฿300/day across 3 ads for 7 days before scaling
