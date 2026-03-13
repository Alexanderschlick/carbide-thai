# Facebook Ads Setup Guide — ThaiCarbide
**For:** Alex
**Estimated time:** 45–60 minutes
**Files to reference:** facebook-ads.md, facebook-targeting.md, facebook-campaign-structure.md

---

## STEP 1 — Create Facebook Business Manager (5 min)

1. Go to **business.facebook.com**
2. Click "Create Account"
3. Fill in:
   - Business name: **ThaiCarbide** (or ThaiCarbide.com)
   - Your name & work email
4. Verify your email
5. You now have a Business Manager account

---

## STEP 2 — Create an Ad Account (3 min)

1. In Business Manager → left menu → **Accounts → Ad Accounts**
2. Click **"Add"** → **"Create a new ad account"**
3. Name: `ThaiCarbide Ads`
4. Currency: **THB (Thai Baht)**
5. Time zone: **Asia/Bangkok**
6. Add payment method (credit card or PromptPay)

---

## STEP 3 — Get Your Pixel ID & Install It (10 min)

1. In Business Manager → left menu → **Data Sources → Pixels**
2. Click **"Add"** → **"Create a Facebook Pixel"**
3. Name: `ThaiCarbide Pixel`
4. Copy the **Pixel ID** (16-digit number, e.g. `1234567890123456`)

**Install on website:**
- The pixel code is already in `index.html` and `checkout.html`
- Just replace `FB_PIXEL_ID` with your real Pixel ID in both files:

```
# In ~/Desktop/carbide-thai/index.html — find and replace:
FB_PIXEL_ID → your actual pixel ID (appears 2 times per file)

# Same in checkout.html
```

Then push to GitHub:
```
cd ~/Desktop/carbide-thai
git add index.html checkout.html
git commit -m "Add real Facebook Pixel ID"
git push
```

**Verify pixel is working:**
- Install [Meta Pixel Helper](https://chrome.google.com/webstore/detail/meta-pixel-helper/) Chrome extension
- Visit thaicarbide.com — should show green pixel firing
- Visit checkout.html — fill and submit form — should show "Lead" event

---

## STEP 4 — Create Audiences (15 min)

### Audience A: CNC Operators (Cold)
1. Business Manager → **Audiences** → **Create Audience → Saved Audience**
2. Name: `CNC Operators Thailand 25-45`
3. Settings:
   - Location: Thailand
   - Age: 25–45
   - Gender: All (male-skew happens naturally)
   - Detailed targeting:
     - Add interests: `CNC machining`, `Metalworking`, `Manufacturing`, `Sandvik Coromant`, `ISCAR`, `Kennametal`
     - Add job titles: `CNC operator`, `Machine operator`
   - **Exclude:** Job titles containing `manager`, `director`, `CEO`

### Audience B: Website Custom Audience (for Lookalike)
1. **Create Audience → Custom Audience → Website**
2. Name: `ThaiCarbide Site Visitors 30d`
3. Pixel: ThaiCarbide Pixel | All website visitors | Last 30 days
4. Save

Then create Lookalike:
1. **Create Audience → Lookalike Audience**
2. Source: ThaiCarbide Site Visitors 30d
3. Country: Thailand | Size: 1%
4. Name: `TC Lookalike 1% TH`

### Audience C: Retargeting (Checkout Abandoners)
1. **Create Audience → Custom Audience → Website**
2. Name: `TC Checkout Abandoners`
3. Include: Visited `checkout.html` in last 14 days
4. Exclude: `Lead` event fired (submitted form)

---

## STEP 5 — Create the Campaign (15 min)

See `facebook-campaign-structure.md` for exact settings.

1. Go to **Ads Manager** (adsmanager.facebook.com)
2. Click **"Create"**
3. Objective: **Leads** (or Messages if LINE OA is connected)
4. Campaign name: `ThaiCarbide — Carbide Scrap TH`
5. Budget: **Campaign Budget Optimization OFF** (set per ad set)
6. Create 3 Ad Sets — see campaign structure file for exact settings

---

## STEP 6 — Connect LINE OA (Optional but recommended)

To use "Messages" objective (sends users to LINE OA):
1. In Business Manager → **Accounts → LINE Account**
2. Connect your LINE Official Account @280uqpab
3. Then in campaign, set destination: LINE OA

---

## STEP 7 — Launch Checklist

- [ ] Pixel firing on thaicarbide.com (check with Pixel Helper)
- [ ] Lead event fires on checkout.html form submit
- [ ] Contact event fires on LINE button click
- [ ] 3 audiences created (A, B, C)
- [ ] 3 ad sets created with correct targeting
- [ ] Ad copy uploaded (copy from facebook-ads.md)
- [ ] Budget set: ฿100/day × 3 ad sets = ฿300/day total
- [ ] Payment method confirmed
- [ ] Campaign published

**Expected first results:** 24–48 hours for delivery to start, 7 days to optimize.

---

## After Launch — Send Nong Your Pixel ID

Once you have your Pixel ID, message me (Nong) or Alex and I'll update the `FB_PIXEL_ID` placeholder in both HTML files and push to GitHub.
