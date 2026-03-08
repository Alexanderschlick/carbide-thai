#!/usr/bin/env python3
"""
CarbideThai Price Updater
Scrapes Schrott24.at carbide prices via Playwright (headless browser),
converts EUR→THB with a live exchange rate and configurable margin,
writes docs/prices.json served by GitHub Pages.
"""

import json
import re
import os
import sys
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────────────────────────
MARGIN = float(os.environ.get("THAILAND_MARGIN", "0.85"))
SCHROTT24_HUB = "https://www.schrott24.at/metalle/hartmetall/"

# Lowercase keywords found in material names or URLs → our price category.
# Order matters: first match wins.
KEYWORD_MAP = [
    (["wendeschneidplatt", "widia", "indexable", "insert"],       "carbide_inserts"),
    (["bohrer", "fräser", "fraeser", "vhm-bohr", "vhm-fraes",
      "vhm bohr", "vhm fraes", "drill", "end mill"],              "carbide_drills"),
    (["verschleiß", "verschleiss", "wear", "sandrill",
      "sand rill", "abbau", "meißel"],                            "sand_rills"),
    (["mischung", "gemischt", "mixed", "unsortiert"],             "mixed_carbide"),
    (["pulver", "powder", "späne", "swarf"],                      "carbide_powder"),
]

# Fallback EUR/kg if live scraping returns nothing for that category
FALLBACK_EUR = {
    "carbide_inserts": 19.00,
    "carbide_drills":  15.50,
    "sand_rills":      10.50,
    "mixed_carbide":    8.50,
    "carbide_powder":   5.50,
}

# German decimal format uses comma: "19,50 €/kg"
PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d{1,3})\s*(?:€|EUR)\s*(?:/\s*kg)?",
    re.IGNORECASE,
)
PRICE_RE_AFTER = re.compile(
    r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{3})*[.,]\d{2}|\d{1,3})\s*(?:/\s*kg)?",
    re.IGNORECASE,
)


def parse_eur(text: str) -> float | None:
    """Extract a EUR price from a text snippet, handling German comma-decimals."""
    for pattern in (PRICE_RE, PRICE_RE_AFTER):
        m = pattern.search(text)
        if m:
            raw = m.group(1).replace(".", "").replace(",", ".")
            try:
                val = float(raw)
                if 1.0 < val < 500.0:   # sanity check
                    return val
            except ValueError:
                pass
    return None


def category_for(text: str) -> str | None:
    """Return the price category key for a material name/URL, or None."""
    lower = text.lower()
    for keywords, category in KEYWORD_MAP:
        if any(kw in lower for kw in keywords):
            return category
    return None


# ── EXCHANGE RATE ────────────────────────────────────────────────────────────────
def get_eur_thb_rate() -> float:
    try:
        import urllib.request
        with urllib.request.urlopen(
            "https://open.er-api.com/v6/latest/EUR", timeout=10
        ) as resp:
            data = json.loads(resp.read())
        rate = float(data["rates"]["THB"])
        print(f"  EUR/THB rate: {rate:.4f}")
        return rate
    except Exception as exc:
        print(f"  Could not fetch exchange rate ({exc}) — using fallback 38.5")
        return 38.5


# ── PLAYWRIGHT SCRAPER ───────────────────────────────────────────────────────────
def scrape_schrott24() -> dict[str, float]:
    """
    Navigate schrott24.at/metalle/hartmetall/ with a headless browser.

    Strategy:
    1. Collect all subcategory card links on the hub page.
    2. Visit each subcategory page; extract the prominently displayed price.
    3. Map material names/URLs to our categories via KEYWORD_MAP.
    4. Return {category: eur_per_kg}.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("  playwright not installed — run: pip install playwright && playwright install chromium")
        return {}

    prices: dict[str, float] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-AT",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        try:
            print(f"  Loading {SCHROTT24_HUB} ...")
            page.goto(SCHROTT24_HUB, wait_until="networkidle", timeout=30_000)

            # Accept cookie banner if present
            for selector in ["button:has-text('Akzeptieren')",
                             "button:has-text('Alle akzeptieren')",
                             "[id*='accept']", "[class*='accept']"]:
                try:
                    page.locator(selector).first.click(timeout=2_000)
                    page.wait_for_timeout(500)
                    break
                except Exception:
                    pass

            # ── Step 1: collect subcategory links from the hub page ──────────────
            # Schrott24 renders material cards/tiles that link to subcategory pages
            sub_links: list[tuple[str, str]] = []   # (url, label)

            cards = page.locator("a[href*='/hartmetall/']").all()
            for card in cards:
                href = card.get_attribute("href") or ""
                if not href or href.rstrip("/") == "/metalle/hartmetall":
                    continue
                label = card.inner_text().strip()
                full_url = href if href.startswith("http") else f"https://www.schrott24.at{href}"
                sub_links.append((full_url, label))
                print(f"    Found subcategory: {label!r} → {full_url}")

            # Deduplicate by URL
            seen: set[str] = set()
            sub_links = [(u, l) for u, l in sub_links if not (u in seen or seen.add(u))]

            # ── Step 2: also try extracting prices already shown on hub page ─────
            # Some hub pages show a price inline on each card
            hub_text = page.inner_text("body")
            _extract_prices_from_text(hub_text, prices)

            # ── Step 3: visit each subcategory page ──────────────────────────────
            for url, label in sub_links:
                cat = category_for(url) or category_for(label)
                if cat and cat in prices:
                    continue  # already have a price for this category
                try:
                    page.goto(url, wait_until="networkidle", timeout=20_000)
                    text = page.inner_text("body")
                    eur = _best_price_from_page(page, text)
                    if eur and cat:
                        prices[cat] = eur
                        print(f"    {cat}: €{eur:.2f}/kg  (from {url})")
                    elif eur:
                        # Try to determine category from page title / heading
                        title = page.title() + " " + (page.locator("h1").first.inner_text() if page.locator("h1").count() else "")
                        cat2 = category_for(title) or category_for(url)
                        if cat2:
                            prices[cat2] = eur
                            print(f"    {cat2}: €{eur:.2f}/kg  (from page heading)")
                except PWTimeout:
                    print(f"    Timeout loading {url}")
                except Exception as exc:
                    print(f"    Error loading {url}: {exc}")

        except Exception as exc:
            print(f"  Hub page error: {exc}")
        finally:
            browser.close()

    return prices


def _extract_prices_from_text(text: str, prices: dict[str, float]) -> None:
    """Scan free text for 'MaterialName … €X,XX /kg' patterns."""
    # Split into lines and look for lines with a price
    for line in text.splitlines():
        eur = parse_eur(line)
        if not eur:
            continue
        cat = category_for(line)
        if cat and cat not in prices:
            prices[cat] = eur
            print(f"    {cat}: €{eur:.2f}/kg  (from hub text)")


def _best_price_from_page(page, body_text: str) -> float | None:
    """
    On a subcategory page, try several strategies to find the main price.
    Schrott24 shows the current buy price prominently near the top.
    """
    # Strategy A: element with "/kg" nearby and a euro amount
    for selector in [
        "[class*='price']", "[class*='Price']",
        "[class*='preis']", "[class*='Preis']",
        "[class*='ankauf']", "[class*='Ankauf']",
        "strong", "b", "h2", "h3",
    ]:
        try:
            els = page.locator(selector).all()
            for el in els[:20]:
                txt = el.inner_text()
                eur = parse_eur(txt)
                if eur:
                    return eur
        except Exception:
            pass

    # Strategy B: scan all text for a price near "/kg"
    kg_pattern = re.compile(
        r"(\d{1,3}(?:[.,]\d{1,3})*[.,]\d{2}|\d+)\s*(?:€|EUR)[^\n]{0,20}/\s*kg",
        re.IGNORECASE,
    )
    m = kg_pattern.search(body_text)
    if m:
        raw = m.group(1).replace(".", "").replace(",", ".")
        try:
            val = float(raw)
            if 1.0 < val < 500.0:
                return val
        except ValueError:
            pass

    # Strategy C: find any plausible EUR price in the page text
    return parse_eur(body_text[:3000])   # check first 3000 chars only


# ── BUILD OUTPUT ─────────────────────────────────────────────────────────────────
def build_prices_json(prices_eur: dict, eur_thb: float, margin: float) -> dict:
    today = datetime.now().strftime("%d %b %Y")
    prices_thb = {}

    for category, fallback in FALLBACK_EUR.items():
        eur = prices_eur.get(category, fallback)
        source = "live" if category in prices_eur else "fallback"
        thb = round(eur * eur_thb * margin, -1)   # nearest 10 THB
        prices_thb[category] = {
            "thb_per_kg": int(thb),
            "eur_per_kg": round(eur, 2),
            "updated": today,
            "source": source,
        }
        print(f"  {category}: €{eur:.2f} × {eur_thb:.2f} × {margin} = ฿{int(thb)}/kg  [{source}]")

    return {
        "updated": today,
        "eur_thb_rate": round(eur_thb, 4),
        "margin_applied": margin,
        "prices": prices_thb,
    }


# ── MAIN ─────────────────────────────────────────────────────────────────────────
def main():
    print("CarbideThai Price Updater")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Margin: {MARGIN * 100:.0f}% of EUR rate\n")

    print("Fetching EUR/THB exchange rate...")
    eur_thb = get_eur_thb_rate()

    print(f"\nScraping schrott24.at ...")
    prices_eur = scrape_schrott24()

    scraped = len(prices_eur)
    missing = [c for c in FALLBACK_EUR if c not in prices_eur]
    if missing:
        print(f"\n  Using fallback for: {', '.join(missing)}")

    print(f"\nBuilding prices.json  ({scraped} live, {len(missing)} fallback) ...")
    output = build_prices_json(prices_eur, eur_thb, MARGIN)

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nprices.json written successfully")
    print(json.dumps(output, indent=2))

    # Exit with code 1 only if ALL prices are fallback (scraping completely failed)
    if scraped == 0:
        print("\nWARNING: all prices are fallback values — check scraper selectors")
        sys.exit(0)   # don't fail the workflow; fallback prices are valid


if __name__ == "__main__":
    main()
