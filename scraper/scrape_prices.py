#!/usr/bin/env python3
"""
CarbideThai Price Updater v3 — HM24 Edition
Scrapes live EUR/kg prices from hartmetallschrott24.de using requests + BeautifulSoup.
Converts EUR -> THB with a live exchange rate.
Applies ThaiCarbide margin formula: buy at ~67% of HM24 market price.

1. Writes prices.json to the repo root (GitHub Pages fallback for admin.html)
2. Upserts all tiers into Supabase /rest/v1/prices (primary source for sell.html)

Required env vars:
  SUPABASE_URL          e.g. https://ltupwgytuayzopnsdvpc.supabase.co
  SUPABASE_SERVICE_KEY  service_role JWT
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Install dependencies: pip install requests beautifulsoup4")
    sys.exit(1)

# -- CONFIG ---------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ltupwgytuayzopnsdvpc.supabase.co")
SB_KEY       = os.environ.get("SUPABASE_SERVICE_KEY", "")
HM24_URL     = "https://hartmetallschrott24.de/"

# ThaiCarbide buys at this ratio of HM24's top-tier price
# When HM24 = 60 EUR, ThaiCarbide base = 40 EUR -> ratio = 0.667
BUY_RATIO = 0.667

# Category multipliers (from lowest to highest, each +5%)
CATEGORY_MULTIPLIERS = {
    "sand_rills":      1.00,  # base (lowest)
    "mixed_carbide":   1.05,  # +5%
    "carbide_drills":  1.10,  # +10%
    "carbide_inserts": 1.15,  # +15% (highest)
}

# Quantity tier discounts (relative to over50 price)
QUANTITY_TIERS = {
    "tier_under20": 0.86,   # < 20 kg
    "tier_mid":     0.94,   # 20-50 kg
    "tier_over50":  1.00,   # 50+ kg (full price)
}

# Material metadata
MATERIAL_META = {
    "carbide_inserts": {
        "name_en": "Carbide Inserts",
        "name_th": "\u0e04\u0e32\u0e23\u0e4c\u0e44\u0e1a\u0e14\u0e4c\u0e2d\u0e34\u0e19\u0e40\u0e2a\u0e34\u0e23\u0e4c\u0e17",
        "hm24_name": "Wendeschneidplatten",
    },
    "carbide_drills": {
        "name_en": "Carbide Drills & Endmills",
        "name_th": "\u0e14\u0e2d\u0e01\u0e2a\u0e27\u0e48\u0e32\u0e19 / \u0e40\u0e2d\u0e47\u0e19\u0e21\u0e34\u0e25 VHM",
        "hm24_name": "Hartmetall-Bohrer",
    },
    "mixed_carbide": {
        "name_en": "Mixed Carbide",
        "name_th": "\u0e04\u0e32\u0e23\u0e4c\u0e44\u0e1a\u0e14\u0e4c\u0e1c\u0e2a\u0e21",
        "hm24_name": "Hartmetall gemischt",
    },
    "sand_rills": {
        "name_en": "Sand Rills / Wear Parts",
        "name_th": "\u0e41\u0e0b\u0e19\u0e14\u0e4c\u0e23\u0e34\u0e25 / \u0e0a\u0e34\u0e49\u0e19\u0e2a\u0e48\u0e27\u0e19\u0e2a\u0e36\u0e01\u0e2b\u0e23\u0e2d",
        "hm24_name": "Stückschrott",
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# -- SCRAPE HM24 ----------------------------------------------------------
def scrape_hm24():
    """
    Scrape hartmetallschrott24.de for current carbide prices.
    Returns dict of category -> {top_eur, all_tiers, hm24_name}
    """
    print(f"  Fetching {HM24_URL}")
    try:
        resp = requests.get(HM24_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ERROR fetching HM24: {exc}")
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    prices = {}

    # Strategy 1: Find price cards with bg-card class
    cards = soup.find_all("div", class_=lambda c: c and "bg-card" in c and "shadow" in c)
    for card in cards:
        card_text = card.get_text(separator="\n", strip=True)

        # Extract all EUR/kg prices from card text
        tier_prices = re.findall(r"(\d+[,\.]\d+)\s*€/kg", card_text)
        if not tier_prices:
            continue

        parsed = []
        for p in tier_prices:
            try:
                val = float(p.replace(",", "."))
                if 1.0 < val < 500.0:
                    parsed.append(val)
            except ValueError:
                continue

        if not parsed:
            continue

        top_price = max(parsed)

        # Match card to our material categories
        for key, meta in MATERIAL_META.items():
            hm24_name = meta["hm24_name"].lower()
            if hm24_name in card_text.lower():
                prices[key] = {
                    "top_eur": top_price,
                    "all_tiers": sorted(parsed),
                    "hm24_name": meta["hm24_name"],
                }
                print(f"    {meta['hm24_name']}: tiers {sorted(parsed)} -> top {top_price:.2f} EUR/kg")
                break

    # Strategy 2: Fallback - parse page text for price mentions
    if not prices:
        print("  Card parsing failed, trying ticker fallback...")
        page_text = soup.get_text()
        for key, meta in MATERIAL_META.items():
            pattern = re.escape(meta["hm24_name"]) + r"[^€]*ca\.\s*(\d+[,\.]\d+)\s*€/kg"
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                val = float(match.group(1).replace(",", "."))
                prices[key] = {
                    "top_eur": val,
                    "all_tiers": [val],
                    "hm24_name": meta["hm24_name"],
                }
                print(f"    {meta['hm24_name']}: ticker {val:.2f} EUR/kg")

    return prices


# -- EXCHANGE RATE ---------------------------------------------------------
def get_eur_thb_rate():
    try:
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/EUR", timeout=10
        ) as resp:
            data = json.loads(resp.read())
        rate = float(data["rates"]["THB"])
        print(f"  EUR/THB: {rate:.4f}")
        return rate
    except Exception as exc:
        print(f"  Exchange rate error ({exc}) -- using fallback 38.0")
        return 38.0


# -- COMPUTE PRICES --------------------------------------------------------
def round50(val):
    """Round to nearest 50 THB."""
    return int(round(val / 50) * 50)


def compute_thai_prices(hm24_prices, eur_thb):
    """
    Compute ThaiCarbide buying prices from HM24 market prices.
    Formula: base_eur = HM24_avg_top * 0.667, then category multiplier,
    then convert to THB, then quantity tier discounts.
    """
    carbide_prices = [p["top_eur"] for k, p in hm24_prices.items() if k != "hss"]
    if not carbide_prices:
        print("  WARNING: No HM24 prices found, using fallback 60 EUR/kg")
        hm24_reference = 60.0
    else:
        hm24_reference = sum(carbide_prices) / len(carbide_prices)

    print(f"\n  HM24 reference price: {hm24_reference:.2f} EUR/kg")
    base_eur = hm24_reference * BUY_RATIO
    print(f"  ThaiCarbide base EUR: {base_eur:.2f} EUR/kg (ratio {BUY_RATIO})")

    results = {}
    best_teaser = 0

    for category, multiplier in CATEGORY_MULTIPLIERS.items():
        cat_eur = base_eur * multiplier
        cat_thb_over50 = round50(cat_eur * eur_thb)

        tiers = {}
        for tier_name, tier_ratio in QUANTITY_TIERS.items():
            tiers[tier_name] = round50(cat_thb_over50 * tier_ratio)

        if cat_thb_over50 > best_teaser:
            best_teaser = cat_thb_over50

        meta = MATERIAL_META[category]
        hm24_specific = hm24_prices.get(category, {}).get("top_eur", hm24_reference)

        results[category] = {
            "hm24_eur": hm24_specific,
            "buy_eur": round(cat_eur, 2),
            "tiers": tiers,
            "name_en": meta["name_en"],
            "name_th": meta["name_th"],
        }

        print(
            f"  {category}: HM24 {hm24_specific:.2f} EUR -> buy {cat_eur:.2f} EUR "
            f"-> {tiers['tier_under20']}/{tiers['tier_mid']}/{tiers['tier_over50']} THB "
            f"(under20/mid/over50)"
        )

    return results, best_teaser


# -- BUILD OUTPUT ----------------------------------------------------------
def build_output(results, best_teaser, hm24_prices, eur_thb):
    now_iso     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    now_display = datetime.now(timezone.utc).strftime("%d %b %Y")

    prices_section = {}
    supabase_rows  = []

    for category, data in results.items():
        tiers = data["tiers"]

        prices_section[category] = {
            "thb_per_kg": tiers["tier_over50"],
            "name_en":    data["name_en"],
            "name_th":    data["name_th"],
            "hm24_eur":   data["hm24_eur"],
            "buy_eur":    data["buy_eur"],
            "tiers":      tiers,
        }

        supabase_rows.append({
            "key":          category,
            "name_en":      data["name_en"],
            "name_th":      data["name_th"],
            "teaser_thb":   best_teaser,
            "tier_under20": tiers["tier_under20"],
            "tier_mid":     tiers["tier_mid"],
            "tier_over50":  tiers["tier_over50"],
            "updated_at":   now_iso,
        })

    hm24_summary = {}
    for k, v in hm24_prices.items():
        hm24_summary[k] = {"eur_per_kg": v["top_eur"], "name": v["hm24_name"]}

    prices_json = {
        "updated":         now_iso,
        "updated_display": now_display,
        "source":          "hartmetallschrott24.de",
        "eur_thb_rate":    round(eur_thb, 4),
        "buy_ratio":       BUY_RATIO,
        "hm24_prices":     hm24_summary,
        "teaser_price":    best_teaser,
        "teaser_material": "carbide_inserts",
        "prices":          prices_section,
    }

    return prices_json, supabase_rows


# -- SUPABASE UPSERT -------------------------------------------------------
def upsert_supabase(rows, url, key):
    if not key:
        print("  SUPABASE_SERVICE_KEY not set -- skipping Supabase upsert")
        return False

    endpoint = f"{url}/rest/v1/prices"
    body     = json.dumps(rows).encode()
    req      = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "Prefer":        "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
        print(f"  Supabase upsert -> HTTP {status} OK")
        return True
    except Exception as exc:
        print(f"  Supabase upsert error: {exc}")
        return False


# -- MAIN ------------------------------------------------------------------
def main():
    print("CarbideThai Price Updater v3 -- HM24 Edition")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Buy ratio: {BUY_RATIO} of HM24 market price\n")

    print("Fetching EUR/THB exchange rate...")
    eur_thb = get_eur_thb_rate()

    print("\nScraping hartmetallschrott24.de...")
    hm24_prices = scrape_hm24()

    scraped = len(hm24_prices)
    if scraped == 0:
        print("\nWARNING: Could not scrape any HM24 prices!")
        print("Using fallback: 60 EUR/kg for all categories")
        for key in MATERIAL_META:
            hm24_prices[key] = {
                "top_eur": 60.0,
                "all_tiers": [50.0, 55.0, 60.0],
                "hm24_name": MATERIAL_META[key]["hm24_name"],
            }

    print(f"\nComputing ThaiCarbide prices ({scraped} categories scraped)...")
    results, best_teaser = compute_thai_prices(hm24_prices, eur_thb)

    print(f"\nBuilding output...")
    prices_json, supabase_rows = build_output(results, best_teaser, hm24_prices, eur_thb)

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(prices_json, f, indent=2, ensure_ascii=False)
    print("\nprices.json written:")
    print(json.dumps(prices_json, indent=2, ensure_ascii=False))

    print(f"\nUpserting {len(supabase_rows)} rows into Supabase...")
    upsert_supabase(supabase_rows, SUPABASE_URL, SB_KEY)

    print(f"\nDone! Teaser price: {best_teaser} THB/kg")


if __name__ == "__main__":
    main()
