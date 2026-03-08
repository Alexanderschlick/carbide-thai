#!/usr/bin/env python3
"""
CarbideThai Price Updater
Scrapes live EUR/kg prices from schrott24.at using requests + BeautifulSoup
(the site is Gatsby-rendered, so prices are in static HTML — no headless browser needed).
Converts EUR → THB with a live exchange rate and configurable margin.
Writes prices.json to the repo root, served by GitHub Pages.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Install dependencies: pip install requests beautifulsoup4")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────────
MARGIN = float(os.environ.get("THAILAND_MARGIN", "1.0"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-AT,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Target pages — primary URL first, fallback second (if primary 404s)
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


# ── PRICE EXTRACTION ─────────────────────────────────────────────────────────
def extract_price(soup: "BeautifulSoup") -> float | None:
    """
    Extract the category's own EUR/kg price from a schrott24.at product page.

    Page structure (Gatsby SSR):
      - spans with class containing 'singlePrice'  → THIS category's price tiers
        (e.g. tier1=22.05, tier2=23.00, tier3=25.00 for inserts)
      - spans with class containing 'card__priceValue' → related-product cards
        shown below (belong to OTHER categories — must be excluded)

    Strategy A: find all 'singlePrice' spans, return the maximum value
      (= highest tier = the "Ankaufpreise bis zu" top price).

    Strategy B: fallback — first 'priceValue' span on the page
      (less precise but still correct if A finds nothing).

    Class names include a Gatsby hash suffix (e.g. singlePrice--4f8c2) that
    could change on a site rebuild; we match on the stable keyword only.
    """

    # Strategy A — all singlePrice spans belong to THIS category's price box
    # BS4 passes the class attribute as a string to the lambda
    single_spans = soup.find_all(
        "span", class_=lambda c: c and "singlePrice" in c
    )
    if single_spans:
        parsed = [_parse_eur(s.get_text(strip=True)) for s in single_spans]
        tiers = [p for p in parsed if p]
        if tiers:
            val = max(tiers)
            print(f"    [A] singlePrice tiers {sorted(tiers)} → max €{val:.2f}")
            return val

    # Strategy B — first priceValue span (could be a card, so only use as fallback)
    pv_span = soup.find(
        "span", class_=lambda c: c and "priceValue" in c
    )
    if pv_span:
        val = _parse_eur(pv_span.get_text(strip=True))
        if val:
            print(f"    [B] priceValue fallback → €{val:.2f}")
            return val

    return None


def _parse_eur(text: str) -> float | None:
    """Parse a German-format decimal string like '25,00' or '25.00' into float."""
    # Remove currency symbols and whitespace
    cleaned = re.sub(r"[€EUReur\s]", "", text)
    # German decimal comma → dot
    cleaned = cleaned.replace(",", ".")
    # Strip trailing /kg or similar
    cleaned = re.sub(r"/.*$", "", cleaned).strip()
    try:
        val = float(cleaned)
        if 1.0 < val < 500.0:
            return val
    except ValueError:
        pass
    return None


# ── FETCH PAGE ────────────────────────────────────────────────────────────────
def fetch_price(category: str, urls: list[str]) -> float | None:
    for url in urls:
        try:
            print(f"  Fetching {url}")
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 404:
                print(f"    404 — trying next URL")
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
def get_eur_thb_rate() -> float:
    try:
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/EUR", timeout=10
        ) as resp:
            data = json.loads(resp.read())
        rate = float(data["rates"]["THB"])
        print(f"  EUR/THB: {rate:.4f}")
        return rate
    except Exception as exc:
        print(f"  Exchange rate error ({exc}) — using fallback 38.5")
        return 38.5


# ── BUILD OUTPUT ──────────────────────────────────────────────────────────────
def build_prices_json(prices_eur: dict, eur_thb: float, margin: float) -> dict:
    today = datetime.now().strftime("%d %b %Y")
    prices_thb = {}

    for category, fallback_eur in FALLBACK_EUR.items():
        eur = prices_eur.get(category, fallback_eur)
        source = "live" if category in prices_eur else "fallback"
        thb = round(eur * eur_thb * margin, -1)   # round to nearest 10 THB
        prices_thb[category] = {
            "thb_per_kg": int(thb),
            "eur_per_kg": round(eur, 2),
            "updated": today,
            "source": source,
        }
        print(f"  {category}: €{eur:.2f} × {eur_thb:.4f} × {margin} = ฿{int(thb)}/kg  [{source}]")

    return {
        "updated": today,
        "eur_thb_rate": round(eur_thb, 4),
        "margin_applied": margin,
        "prices": prices_thb,
    }


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("CarbideThai Price Updater")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Margin: {MARGIN * 100:.0f}% of EUR rate\n")

    print("Fetching EUR/THB exchange rate...")
    eur_thb = get_eur_thb_rate()

    print("\nScraping schrott24.at prices...")
    prices_eur: dict[str, float] = {}
    for category, urls in PAGES.items():
        print(f"\n[{category}]")
        val = fetch_price(category, urls)
        if val:
            prices_eur[category] = val
        else:
            print(f"  Using fallback: €{FALLBACK_EUR[category]:.2f}")

    scraped = len(prices_eur)
    missing = [c for c in FALLBACK_EUR if c not in prices_eur]
    if missing:
        print(f"\n  Fallback used for: {', '.join(missing)}")

    print(f"\nBuilding prices.json  ({scraped} live, {len(missing)} fallback) ...")
    output = build_prices_json(prices_eur, eur_thb, MARGIN)

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("\nprices.json written:")
    print(json.dumps(output, indent=2, ensure_ascii=False))

    if scraped == 0:
        print("\nWARNING: all prices are fallback — check selectors / network")
        sys.exit(0)   # don't fail the workflow; fallback prices are valid


if __name__ == "__main__":
    main()
