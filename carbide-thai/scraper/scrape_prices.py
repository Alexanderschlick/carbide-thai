#!/usr/bin/env python3
"""
CarbideThai Price Updater
Scrapes Schrott24.at prices, converts EUR→THB, applies Thailand margin,
then writes prices.json which the website reads daily.
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

# ─── CONFIG ────────────────────────────────────────────────────────────────────
MARGIN = float(os.environ.get("THAILAND_MARGIN", "0.82"))  # 0.82 = pay 82% of EUR rate
# Set your margin in GitHub Secrets as THAILAND_MARGIN (e.g. 0.75 = 75%)

SCHROTT24_URL = "https://www.schrott24.at/"

# Map Schrott24 material names → CarbideThai categories
# Update these keys to match what actually appears on Schrott24
MATERIAL_MAP = {
    "Hartmetall":        "carbide_inserts",    # Solid carbide / inserts
    "Wolframcarbid":     "carbide_inserts",
    "Hartmetallbohrer":  "carbide_drills",     # Carbide drills
    "Fräser":            "carbide_drills",
    "Verschleißteile":   "sand_rills",         # Wear parts / sand rills
    "Hartmetallmischung":"mixed_carbide",       # Mixed carbide
    "Carbidpulver":      "carbide_powder",      # Powder / swarf
}

# Fallback prices (EUR/kg) if scraping fails — update these manually
FALLBACK_EUR = {
    "carbide_inserts": 18.50,
    "carbide_drills":  15.00,
    "sand_rills":      10.50,
    "mixed_carbide":    8.20,
    "carbide_powder":   5.50,
}

# ─── GET EUR/THB EXCHANGE RATE ──────────────────────────────────────────────────
def get_eur_thb_rate():
    try:
        r = requests.get(
            "https://open.er-api.com/v6/latest/EUR",
            timeout=10
        )
        data = r.json()
        rate = data["rates"]["THB"]
        print(f"✅ EUR/THB rate: {rate}")
        return rate
    except Exception as e:
        print(f"⚠️  Could not fetch exchange rate: {e} — using fallback 38.5")
        return 38.5  # fallback rate

# ─── SCRAPE SCHROTT24 ──────────────────────────────────────────────────────────
def scrape_schrott24():
    prices_eur = {}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; CarbideThai-PriceBot/1.0)"
        }
        r = requests.get(SCHROTT24_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Schrott24 typically shows prices in elements with data attributes or
        # price tables — adjust selectors if their HTML changes
        # Look for price elements (update selector based on actual HTML structure)
        price_elements = soup.select("[data-price], .price-value, .schrottpreis")

        for el in price_elements:
            name = el.get("data-material", "") or el.get_text(strip=True)
            price_text = el.get("data-price", "") or el.get_text(strip=True)
            # Extract numeric price
            price_str = "".join(c for c in price_text if c.isdigit() or c in ".,")
            if price_str:
                price = float(price_str.replace(",", "."))
                # Match to our categories
                for keyword, category in MATERIAL_MAP.items():
                    if keyword.lower() in name.lower():
                        prices_eur[category] = price
                        print(f"✅ Scraped: {category} = €{price}/kg")
                        break

        if not prices_eur:
            print("⚠️  No prices scraped from page — check selectors. Using fallbacks.")

    except Exception as e:
        print(f"⚠️  Scraping failed: {e}")

    # Fill any missing categories with fallbacks
    for category, fallback in FALLBACK_EUR.items():
        if category not in prices_eur:
            prices_eur[category] = fallback
            print(f"📌 Using fallback for {category}: €{fallback}/kg")

    return prices_eur

# ─── BUILD PRICES JSON ─────────────────────────────────────────────────────────
def build_prices_json(prices_eur, eur_thb, margin):
    today = datetime.now().strftime("%d %b %Y")
    prices_thb = {}

    for category, eur_price in prices_eur.items():
        thb = round(eur_price * eur_thb * margin, -1)  # Round to nearest 10 THB
        prices_thb[category] = {
            "thb_per_kg": int(thb),
            "eur_per_kg": round(eur_price, 2),
            "updated": today,
        }
        print(f"💰 {category}: €{eur_price} × {eur_thb:.2f} × {margin} = ฿{int(thb)}/kg")

    return {
        "updated": today,
        "eur_thb_rate": round(eur_thb, 4),
        "margin_applied": margin,
        "prices": prices_thb
    }

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("🚀 CarbideThai Price Updater starting...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"📊 Margin: {MARGIN * 100:.0f}% of EUR rate\n")

    eur_thb = get_eur_thb_rate()
    prices_eur = scrape_schrott24()
    output = build_prices_json(prices_eur, eur_thb, MARGIN)

    # Write to docs/prices.json (served by GitHub Pages)
    os.makedirs("docs", exist_ok=True)
    with open("docs/prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✅ prices.json written successfully")
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
