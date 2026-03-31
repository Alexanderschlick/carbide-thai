#!/usr/bin/env python3
"""
CarbideThai Price Updater v2
Scrapes live EUR/kg prices from schrott24.at using requests + BeautifulSoup.
Converts EUR -> THB with a live exchange rate.
1. Writes prices.json to the repo root (GitHub Pages fallback for admin.html)
2. Upserts teaser_thb into Supabase /rest/v1/prices (primary source for sell.html)

Required env vars:
  SUPABASE_URL          e.g. https://ltupwgytuayzopnsdvpc.supabase.co
  SUPABASE_SERVICE_KEY  service_role JWT
  THAILAND_MARGIN       float multiplier, default 1.0 (optional)
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

# ── CONFIG ────────────────────────────────────────────────────────────────────
MARGIN       = float(os.environ.get("THAILAND_MARGIN") or "1.0")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ltupwgytuayzopnsdvpc.supabase.co")
SB_KEY       = os.environ.get("SUPABASE_SERVICE_KEY", "")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Target pages -- primary URL first, fallback second (if primary 404s)
PAGES = {
    "carbide_inserts": [
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/wendeschneidplatten-widia/",
    ],
    "carbide_drills": [
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/hartmetall-bohrer-und-fraeser/",
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/vhm-werkzeuge-bohrer-fraeser/",
    ],
    "mixed_carbide": [
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/hartmetall-gemischt/",
    ],
    "sand_rills": [
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/sandrill-abbaumeiszel/",
        "https://www.schrott24.at/altmetall-ankauf/hartmetall-hss/sandrill/",
    ],
}

FALLBACK_EUR = {
    "carbide_inserts": 25.00,
    "carbide_drills":  26.00,
    "mixed_carbide":   22.00,
    "sand_rills":      14.00,
}

# Material metadata for prices.json and Supabase upsert
# tier_ratios: proportion of teaser_thb (over50 rate) for each tier.
# None = no tiers for this material (flat rate).
MATERIAL_META = {
    "carbide_inserts": {
        "name_en":     "Carbide Inserts",
        "name_th":     "\u0e04\u0e32\u0e23\u0e4c\u0e44\u0e1a\u0e14\u0e4c\u0e2d\u0e34\u0e19\u0e40\u0e2a\u0e34\u0e3a\u0e17",
        "tier_ratios": {"under20": 0.622, "mid": 0.633, "over50": 1.0},
    },
    "carbide_drills": {
        "name_en":     "Carbide Drills & Endmills",
        "name_th":     "\u0e14\u0e2d\u0e01\u0e2a\u0e27\u0e48\u0e32\u0e19 / \u0e40\u0e2d\u0e47\u0e19\u0e21\u0e34\u0e25 VHM",
        "tier_ratios": {"under20": 0.565, "mid": 0.609, "over50": 1.0},
    },
    "mixed_carbide": {
        "name_en":     "Mixed Carbide",
        "name_th":     "\u0e04\u0e32\u0e23\u0e4c\u0e44\u0e1a\u0e14\u0e4c\u0e1c\u0e2a\u0e21",
        "tier_ratios": {"under20": 0.553, "mid": 0.596, "over50": 1.0},
    },
    "sand_rills": {
        "name_en":     "Sand Rills / Wear Parts",
        "name_th":     "\u0e41\u0e0b\u0e19\u0e14\u0e4c\u0e23\u0e34\u0e25 / \u0e0a\u0e34\u0e49\u0e19\u0e2a\u0e48\u0e27\u0e19\u0e2a\u0e36\u0e01\u0e2b\u0e23\u0e2d",
        "tier_ratios": None,
    },
}


# ── PRICE EXTRACTION ─────────────────────────────────────────────────────────
def extract_price(soup):
    """
    Extract EUR/kg price from a schrott24.at product page.
    Strategy A: find all singlePrice spans, return max value (highest tier).
    Strategy B: fallback to first priceValue span on the page.
    """
    single_spans = soup.find_all(
        "span", class_=lambda c: c and "singlePrice" in c
    )
    if single_spans:
        parsed = [_parse_eur(s.get_text(strip=True)) for s in single_spans]
        tiers = [p for p in parsed if p]
        if tiers:
            val = max(tiers)
            print(f"    [A] singlePrice tiers {sorted(tiers)} -> max EUR{val:.2f}")
            return val

    pv_span = soup.find("span", class_=lambda c: c and "priceValue" in c)
    if pv_span:
        val = _parse_eur(pv_span.get_text(strip=True))
        if val:
            print(f"    [B] priceValue fallback -> EUR{val:.2f}")
            return val

    return None


def _parse_eur(text):
    """Parse a German-format decimal string like '25,00' or '25.00' into float."""
    cleaned = re.sub(r"[EUReur\s]", "", text)
    cleaned = cleaned.replace(",", ".")
    cleaned = re.sub(r"/.*$", "", cleaned).strip()
    try:
        val = float(cleaned)
        if 1.0 < val < 500.0:
            return val
    except ValueError:
        pass
    return None


# ── FETCH PAGE ────────────────────────────────────────────────────────────────
def fetch_price(category, urls):
    for url in urls:
        try:
            print(f"  Fetching {url}")
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                print(f"    404 -- trying next URL")
                continue
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            val = extract_price(soup)
            if val:
                return val
            print(f"    No price found in page HTML")
        except requests.RequestException as exc:
            print(f"    Request error: {exc}")
    return None


# ── EXCHANGE RATE ─────────────────────────────────────────────────────────────
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
        print(f"  Exchange rate error ({exc}) -- using fallback 38.5")
        return 38.5


# ── COMPUTE TIERS ─────────────────────────────────────────────────────────────
def _round50(val):
    """Round to nearest 50 THB."""
    return int(round(val / 50) * 50)


def compute_tiers(teaser_thb, ratios):
    """Compute under20/mid/over50 tiers from teaser price using configured ratios."""
    if ratios is None:
        return None
    return {
        "under20": _round50(teaser_thb * ratios["under20"]),
        "mid":     _round50(teaser_thb * ratios["mid"]),
        "over50":  teaser_thb,
    }


# ── BUILD OUTPUT ──────────────────────────────────────────────────────────────
def build_output(prices_eur, eur_thb, margin):
    """
    Returns (prices_json_dict, supabase_rows).
    prices_json_dict: written to prices.json (admin.html GitHub Pages fallback)
    supabase_rows:    upserted into Supabase /rest/v1/prices (sell.html primary)
    """
    now_iso     = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    now_display = datetime.now(timezone.utc).strftime("%d %b %Y")

    prices_section  = {}
    teaser_prices   = {}
    supabase_rows   = []
    best_teaser_key = "carbide_inserts"

    for category, meta in MATERIAL_META.items():
        eur        = prices_eur.get(category, FALLBACK_EUR[category])
        source     = "live" if category in prices_eur else "fallback"
        teaser_thb = _round50(eur * eur_thb * margin)
        tiers      = compute_tiers(teaser_thb, meta["tier_ratios"])

        print(
            f"  {category}: EUR{eur:.2f} x {eur_thb:.4f} x {margin} "
            f"= THB{teaser_thb}/kg  [{source}]"
        )

        # prices.json entry (admin.html fallback format)
        prices_section[category] = {
            "thb_per_kg": teaser_thb,
            "name_en":    meta["name_en"],
            "name_th":    meta["name_th"],
            "tiers":      tiers,
        }
        teaser_prices[category] = {"thb_per_kg": teaser_thb}

        # Supabase row -- use merge-duplicates so existing manual tiers survive
        sb_row = {
            "key":        category,
            "name_en":    meta["name_en"],
            "name_th":    meta["name_th"],
            "teaser_thb": teaser_thb,
            "updated_at": now_iso,
        }
        if tiers:
            sb_row["tier_under20"] = tiers["under20"]
            sb_row["tier_mid"]     = tiers["mid"]
            sb_row["tier_over50"]  = tiers["over50"]
        supabase_rows.append(sb_row)

    teaser_val = prices_section[best_teaser_key]["thb_per_kg"]

    prices_json = {
        "updated":         now_iso,
        "updated_display": now_display,
        "eur_thb_rate":    round(eur_thb, 4),
        "teaser_price":    teaser_val,
        "teaser_material": best_teaser_key,
        "teaser_prices":   teaser_prices,
        "prices":          prices_section,
    }

    return prices_json, supabase_rows


# ── SUPABASE UPSERT ───────────────────────────────────────────────────────────
def upsert_supabase(rows, url, key):
    """
    Upsert rows into Supabase /rest/v1/prices.
    merge-duplicates: only updates fields sent in the payload,
    so existing manual tier values are preserved if client omits them.
    Returns True on success.
    """
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
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        print(f"  Supabase upsert failed: HTTP {exc.code} -- {body_text}")
        return False
    except Exception as exc:
        print(f"  Supabase upsert error: {exc}")
        return False


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("CarbideThai Price Updater v2")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Margin: {MARGIN * 100:.0f}%\n")

    print("Fetching EUR/THB exchange rate...")
    eur_thb = get_eur_thb_rate()

    print("\nScraping schrott24.at prices...")
    prices_eur = {}
    for category, urls in PAGES.items():
        print(f"\n[{category}]")
        val = fetch_price(category, urls)
        if val:
            prices_eur[category] = val
        else:
            print(f"  Using fallback: EUR{FALLBACK_EUR[category]:.2f}")

    scraped = len(prices_eur)
    missing = [c for c in FALLBACK_EUR if c not in prices_eur]
    if missing:
        print(f"\n  Fallback used for: {', '.join(missing)}")

    print(f"\nBuilding output  ({scraped} live, {len(missing)} fallback)...")
    prices_json, supabase_rows = build_output(prices_eur, eur_thb, MARGIN)

    # 1. Write prices.json (admin.html fallback)
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(prices_json, f, indent=2, ensure_ascii=False)
    print("\nprices.json written:")
    print(json.dumps(prices_json, indent=2, ensure_ascii=False))

    # 2. Upsert into Supabase (primary source for sell.html)
    print(f"\nUpserting {len(supabase_rows)} rows into Supabase prices table...")
    upsert_supabase(supabase_rows, SUPABASE_URL, SB_KEY)

    if scraped == 0:
        print("\nWARNING: all prices are fallback -- check selectors / network")
        sys.exit(0)   # don't fail the workflow; fallback prices are still valid


if __name__ == "__main__":
    main()
