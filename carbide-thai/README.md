# CarbideThai.com

Thailand's first online tungsten carbide scrap buying platform.

## Setup (30 minutes, no coding needed)

### Step 1 — GitHub (free)
1. Go to github.com → Sign up free
2. Click "New repository" → name it `carbide-thai` → Public → Create
3. Upload all these files by dragging them in

### Step 2 — Enable GitHub Pages (free hosting)
1. In your repo → Settings → Pages
2. Source: Deploy from branch → Branch: `main` → Folder: `/docs`
3. Save → your site is live at `https://YOUR-USERNAME.github.io/carbide-thai`

### Step 3 — Set Your Margin (GitHub Secret)
1. Settings → Secrets and variables → Actions → New repository secret
2. Name: `THAILAND_MARGIN`
3. Value: `0.82` (means you pay sellers 82% of the EUR Schrott24 rate converted to THB)
   - 0.90 = generous (good for volume)
   - 0.80 = standard margin
   - 0.70 = higher margin

### Step 4 — Formspree (free email notifications)
1. Go to formspree.io → Sign up free
2. New Form → copy the URL (looks like `https://formspree.io/f/xyzabc123`)
3. Open `docs/index.html` → find `YOUR_FORM_ID` → replace with your ID
4. Every order form submission → email to you instantly

### Step 5 — Update Your LINE ID
- In `docs/index.html` find `YOUR_LINE_ID` and replace with your LINE ID
- Sellers click the LINE button and land directly in your chat

### Step 6 — Custom Domain (optional, ~500 THB/year)
1. Buy `carbidethaii.com` from Namecheap
2. In GitHub Pages settings → add your custom domain

---

## How Prices Update Automatically

Every day at 8:00 AM Bangkok time, GitHub Actions:
1. Runs `scraper/scrape_prices.py`
2. Fetches live EUR/THB exchange rate
3. Scrapes Schrott24.at for current carbide prices
4. Applies your Thailand margin
5. Writes `docs/prices.json`
6. Commits and pushes — website updates instantly

Google sees fresh prices every day → better SEO ranking.

## Files

```
carbide-thai/
├── docs/
│   ├── index.html       ← The website
│   └── prices.json      ← Auto-generated daily (don't edit manually)
├── scraper/
│   └── scrape_prices.py ← Price scraper script
├── .github/
│   └── workflows/
│       └── update-prices.yml ← Daily automation
└── README.md
```

## Updating Prices Manually

If you want to update prices without waiting for the daily run:
1. Go to your GitHub repo → Actions tab
2. Click "Daily Price Update" → "Run workflow" → Run
3. Done — prices update within 60 seconds
