#!/usr/bin/env python3
"""ThaiCarbide Daily Business Report - Autonomous email delivery."""
import os, json, smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from urllib.request import Request, urlopen
from urllib.parse import quote

SB_URL = os.environ.get('SUPABASE_URL', '')
SB_KEY = os.environ.get('SUPABASE_KEY', '')
GMAIL_USER = os.environ.get('GMAIL_USER', 'thaicarbide@gmail.com')
GMAIL_PWD  = os.environ.get('GMAIL_APP_PASSWORD', '')
REPORT_TO  = os.environ.get('REPORT_EMAIL', GMAIL_USER)
BKK = timezone(timedelta(hours=7))

def sb_get(table, params=''):
    url = f"{SB_URL}/rest/v1/{table}?{params}"
    req = Request(url, headers={
        'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}'
    })
    try:
        with urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Warning: query to {table} failed: {e}")
        return []

def sb_count(table, params=''):
    """Exact row count via Content-Range header (Supabase caps row fetches at 1000)."""
    url = f"{SB_URL}/rest/v1/{table}?{params}"
    req = Request(url, headers={
        'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}',
        'Prefer': 'count=exact', 'Range-Unit': 'items', 'Range': '0-0'
    })
    try:
        with urlopen(req, timeout=15) as r:
            total = r.headers.get('Content-Range', '').split('/')[-1]
            return int(total) if total.isdigit() else 0
    except Exception as e:
        print(f"Warning: count query to {table} failed: {e}")
        return 0

def sb_get_all(table, params='', page_size=1000):
    """Fetch all rows with Range pagination (avoids the 1000-row cap)."""
    rows, start = [], 0
    while True:
        url = f"{SB_URL}/rest/v1/{table}?{params}"
        req = Request(url, headers={
            'apikey': SB_KEY, 'Authorization': f'Bearer {SB_KEY}',
            'Range-Unit': 'items', 'Range': f'{start}-{start + page_size - 1}'
        })
        try:
            with urlopen(req, timeout=15) as r:
                batch = json.loads(r.read())
        except Exception as e:
            print(f"Warning: paged query to {table} failed: {e}")
            break
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows

def get_eur_thb_rate():
    """Fetch current EUR/THB exchange rate from free API."""
    try:
        url = "https://open.er-api.com/v6/latest/EUR"
        req = Request(url)
        with urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data.get('rates', {}).get('THB', 38.5)
    except Exception as e:
        print(f"Warning: exchange rate fetch failed: {e}")
        return 38.5

def fmt_baht(n):
    if n is None: return '-'
    return f"฿{n:,.0f}"

def fmt_eur(n):
    if n is None: return '-'
    return f"€{n:,.2f}"

def thb_to_eur(thb, rate):
    if thb is None or rate is None or rate == 0: return None
    return thb / rate

def main():
    now = datetime.now(BKK)
    yesterday_dt = now - timedelta(hours=24)
    yesterday = yesterday_dt.strftime('%Y-%m-%dT%H:%M:%S')
    seven_days_ago = (now - timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S')

    eur_thb = get_eur_thb_rate()
    print(f"EUR/THB rate: {eur_thb:.2f}")

    prices = sb_get('prices', 'select=*&order=key')
    lead_params = f'select=*&created_at=gte.{quote(yesterday)}&order=created_at.desc'
    new_leads = sb_get('leads', lead_params)
    parcels = sb_get_all('parcels', 'select=*')
    pending = [p for p in parcels if p.get('status') in ('pending','delivered','weighed')]

    total_views_24h = sb_count('page_views', f'select=id&created_at=gte.{quote(yesterday)}')

    total_views_7d = sb_count('page_views', f'select=id&created_at=gte.{quote(seven_days_ago)}')

    total_views_all = sb_count('page_views', 'select=id')

    views_7d_full = sb_get_all('page_views', f'select=utm_source,referrer,device&created_at=gte.{quote(seven_days_ago)}')
    source_counts = {}
    device_counts = {}
    for v in views_7d_full:
        src = v.get('utm_source') or 'direct'
        if src == 'direct' and v.get('referrer'):
            ref = v.get('referrer', '')
            if 'google' in ref: src = 'google (organic)'
            elif 'facebook' in ref: src = 'facebook (organic)'
            elif 'line' in ref: src = 'line'
            else: src = 'referral'
        source_counts[src] = source_counts.get(src, 0) + 1
        dev = v.get('device') or 'unknown'
        device_counts[dev] = device_counts.get(dev, 0) + 1

    total_leads = sb_count('leads', 'select=id')
    settled = [p for p in parcels if p.get('status') == 'settled']
    total_kg = sum(float(p.get('actual_kg') or 0) for p in settled)
    total_comm = sum(float(p.get('commission_total') or 0) for p in settled)

    order_params = f'select=*&created_at=gte.{quote(yesterday)}&order=created_at.desc'
    new_orders = sb_get('orders', order_params)

    status_counts = {}
    for p in parcels:
        s = p.get('status', 'unknown')
        if s not in status_counts: status_counts[s] = {'count': 0, 'kg': 0}
        status_counts[s]['count'] += 1
        status_counts[s]['kg'] += float(p.get('actual_kg') or p.get('estimated_kg') or 0)

    conversion_rate = f"{(total_leads / total_views_all * 100):.1f}%" if total_views_all > 0 else "n/a"

    price_rows = ''
    for p in prices:
        teaser_thb = p.get('teaser_thb')
        t20_thb = p.get('tier_under20')
        tmid_thb = p.get('tier_mid')
        t50_thb = p.get('tier_over50')
        teaser_eur = thb_to_eur(float(teaser_thb) if teaser_thb else None, eur_thb)
        t20_eur = thb_to_eur(float(t20_thb) if t20_thb else None, eur_thb)
        tmid_eur = thb_to_eur(float(tmid_thb) if tmid_thb else None, eur_thb)
        t50_eur = thb_to_eur(float(t50_thb) if t50_thb else None, eur_thb)
        price_rows += f"""<tr>
<td style="padding:8px;border-bottom:1px solid #eee;font-weight:600">{p.get('name_en','')}</td>
<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(teaser_thb)}<br><span style="color:#888;font-size:11px">{fmt_eur(teaser_eur)}</span></td>
<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(t20_thb)}<br><span style="color:#888;font-size:11px">{fmt_eur(t20_eur)}</span></td>
<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(tmid_thb)}<br><span style="color:#888;font-size:11px">{fmt_eur(tmid_eur)}</span></td>
<td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(t50_thb)}<br><span style="color:#888;font-size:11px">{fmt_eur(t50_eur)}</span></td>
</tr>"""

    lead_section = ''
    if new_leads:
        lead_items = ''
        for l in new_leads[:10]:
            lead_items += f"<li><b>{l.get('display_name','?')}</b> - {l.get('material_type','')} ({l.get('weight_kg','?')}kg) via {l.get('source','')}</li>"
        lead_section = f"<h3 style='color:#27ae60'>New Leads: {len(new_leads)}</h3><ul>{lead_items}</ul>"
    else:
        lead_section = "<p style='color:#999'>No new leads in the last 24 hours.</p>"

    order_section = ''
    if new_orders:
        order_items = ''
        for o in new_orders[:10]:
            amt = o.get('total_amount')
            amt_eur = thb_to_eur(float(amt) if amt else None, eur_thb)
            order_items += f"<li><b>{o.get('name','?')}</b> - {o.get('material','')} ({o.get('weight_ordered','?')}kg) - {fmt_baht(amt)} ({fmt_eur(amt_eur)}) - {o.get('delivery_method','')}</li>"
        order_section = f"<h3 style='color:#2980b9'>New Orders: {len(new_orders)}</h3><ul>{order_items}</ul>"

    status_section = ''
    for s, d in sorted(status_counts.items()):
        status_section += f"<tr><td style='padding:6px 8px;border-bottom:1px solid #eee;text-transform:capitalize'>{s}</td><td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:center'>{d['count']}</td><td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:right'>{d['kg']:.1f} kg</td></tr>"

    pending_section = ''
    if pending:
        for p in pending:
            pending_section += f"<li><b>{p.get('seller_name','?')}</b> - {p.get('material_type','')} ({p.get('estimated_kg','?')}kg) - Status: {p.get('status','')} - Added: {str(p.get('created_at',''))[:10]}</li>"
        pending_section = f"<h3>Pending Actions ({len(pending)})</h3><ul>{pending_section}</ul>"

    source_rows = ''
    for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
        pct = f"{cnt / len(views_7d_full) * 100:.0f}%" if views_7d_full else "0%"
        source_rows += f"<tr><td style='padding:4px 8px;border-bottom:1px solid #eee'>{src}</td><td style='padding:4px 8px;border-bottom:1px solid #eee;text-align:center'>{cnt}</td><td style='padding:4px 8px;border-bottom:1px solid #eee;text-align:right'>{pct}</td></tr>"

    device_rows = ''
    for dev, cnt in sorted(device_counts.items(), key=lambda x: -x[1]):
        pct = f"{cnt / len(views_7d_full) * 100:.0f}%" if views_7d_full else "0%"
        device_rows += f"<tr><td style='padding:4px 8px;border-bottom:1px solid #eee;text-transform:capitalize'>{dev}</td><td style='padding:4px 8px;border-bottom:1px solid #eee;text-align:center'>{cnt}</td><td style='padding:4px 8px;border-bottom:1px solid #eee;text-align:right'>{pct}</td></tr>"

    html = f"""<html><body style="font-family:-apple-system,sans-serif;max-width:650px;margin:0 auto;padding:20px;color:#333">
<div style="background:#1a1a2e;color:#fff;padding:20px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">Thai<span style="color:#27ae60">Carbide</span> Daily Report</h1>
  <p style="margin:4px 0 0;color:#bdc3c7;font-size:13px">{now.strftime('%A, %d %B %Y - %H:%M')} (Bangkok)</p>
  <p style="margin:2px 0 0;color:#95a5a6;font-size:11px">EUR/THB: {eur_thb:.2f}</p>
</div>
<div style="background:#fff;border:1px solid #e0e0e0;border-top:none;padding:20px;border-radius:0 0 8px 8px">

<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
  <div style="flex:1;min-width:80px;background:#eafaf1;border-radius:6px;padding:12px;text-align:center">
    <div style="font-size:11px;color:#666;text-transform:uppercase">Total Leads</div>
    <div style="font-size:24px;font-weight:700;color:#27ae60">{total_leads}</div>
  </div>
  <div style="flex:1;min-width:80px;background:#ebf5fb;border-radius:6px;padding:12px;text-align:center">
    <div style="font-size:11px;color:#666;text-transform:uppercase">Settled kg</div>
    <div style="font-size:24px;font-weight:700;color:#2980b9">{total_kg:.1f}</div>
  </div>
  <div style="flex:1;min-width:80px;background:#fef9e7;border-radius:6px;padding:12px;text-align:center">
    <div style="font-size:11px;color:#666;text-transform:uppercase">Commission</div>
    <div style="font-size:24px;font-weight:700;color:#d68910">{fmt_baht(total_comm)}</div>
    <div style="font-size:11px;color:#999">{fmt_eur(thb_to_eur(total_comm, eur_thb))}</div>
  </div>
</div>

<div style="background:#f8f9fa;border-radius:8px;padding:16px;margin-bottom:20px;border:1px solid #e9ecef">
  <h3 style="margin:0 0 12px;font-size:15px;color:#495057">Website Analytics</h3>
  <div style="display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap">
    <div style="flex:1;min-width:80px;background:#fff;border-radius:6px;padding:10px;text-align:center;border:1px solid #dee2e6">
      <div style="font-size:10px;color:#666;text-transform:uppercase">Views (24h)</div>
      <div style="font-size:22px;font-weight:700;color:#6f42c1">{total_views_24h}</div>
    </div>
    <div style="flex:1;min-width:80px;background:#fff;border-radius:6px;padding:10px;text-align:center;border:1px solid #dee2e6">
      <div style="font-size:10px;color:#666;text-transform:uppercase">Views (7d)</div>
      <div style="font-size:22px;font-weight:700;color:#6f42c1">{total_views_7d}</div>
    </div>
    <div style="flex:1;min-width:80px;background:#fff;border-radius:6px;padding:10px;text-align:center;border:1px solid #dee2e6">
      <div style="font-size:10px;color:#666;text-transform:uppercase">Total Views</div>
      <div style="font-size:22px;font-weight:700;color:#6f42c1">{total_views_all}</div>
    </div>
    <div style="flex:1;min-width:80px;background:#fff;border-radius:6px;padding:10px;text-align:center;border:1px solid #dee2e6">
      <div style="font-size:10px;color:#666;text-transform:uppercase">Conv. Rate</div>
      <div style="font-size:22px;font-weight:700;color:#e83e8c">{conversion_rate}</div>
    </div>
  </div>

  {'<h4 style="margin:0 0 8px;font-size:13px;color:#495057">Traffic Sources (7d)</h4><table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px"><thead><tr style="background:#e9ecef"><th style="padding:4px 8px;text-align:left">Source</th><th style="padding:4px 8px;text-align:center">Visits</th><th style="padding:4px 8px;text-align:right">%</th></tr></thead><tbody>' + source_rows + '</tbody></table>' if source_rows else ''}

  {'<h4 style="margin:0 0 8px;font-size:13px;color:#495057">Devices (7d)</h4><table style="width:100%;border-collapse:collapse;font-size:12px"><thead><tr style="background:#e9ecef"><th style="padding:4px 8px;text-align:left">Device</th><th style="padding:4px 8px;text-align:center">Visits</th><th style="padding:4px 8px;text-align:right">%</th></tr></thead><tbody>' + device_rows + '</tbody></table>' if device_rows else ''}
</div>

<h3>Current Prices (THB / <span style="color:#888">EUR</span>)</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#f5f6fa">
  <th style="padding:8px;text-align:left">Material</th>
  <th style="padding:8px;text-align:right">Teaser</th>
  <th style="padding:8px;text-align:right">&lt;20kg</th>
  <th style="padding:8px;text-align:right">20-50kg</th>
  <th style="padding:8px;text-align:right">&gt;50kg</th>
</tr></thead>
<tbody>{price_rows if price_rows else '<tr><td colspan=5 style="padding:8px;color:#999">No price data</td></tr>'}</tbody></table>

{lead_section}
{order_section}

<h3>Parcel Status</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead><tr style="background:#f5f6fa">
  <th style="padding:6px 8px;text-align:left">Status</th>
  <th style="padding:6px 8px;text-align:center">Count</th>
  <th style="padding:6px 8px;text-align:right">Weight</th>
</tr></thead>
<tbody>{status_section if status_section else '<tr><td colspan=3 style="padding:8px;color:#999">No parcels yet</td></tr>'}</tbody></table>

{pending_section}

<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="font-size:11px;color:#999">Auto-generated by ThaiCarbide GitHub Actions. <a href="https://thaicarbide.com/bo.html">Open Dashboard</a></p>
</div></body></html>"""

    if not GMAIL_PWD:
        print("GMAIL_APP_PASSWORD not set - printing report to stdout")
        print(html)
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"ThaiCarbide Daily Report - {now.strftime('%d %b %Y')}"
    msg['From']    = f"ThaiCarbide Report <{GMAIL_USER}>"
    msg['To']      = REPORT_TO
    msg.attach(MIMEText(html, 'html'))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx) as s:
        s.login(GMAIL_USER, GMAIL_PWD)
        s.sendmail(GMAIL_USER, REPORT_TO, msg.as_string())
    print(f"Report sent to {REPORT_TO}")

if __name__ == '__main__':
    main()
