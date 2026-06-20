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
GMAIL_PWD = os.environ.get('GMAIL_APP_PASSWORD', '')
REPORT_TO = os.environ.get('REPORT_EMAIL', GMAIL_USER)
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

def fmt_baht(n):
    if n is None: return '-'
    return f"\u0e3f{n:,.0f}"

def main():
    now = datetime.now(BKK)
    yesterday_dt = now - timedelta(hours=24)
    yesterday = yesterday_dt.strftime('%Y-%m-%dT%H:%M:%S')

    # 1. Prices
    prices = sb_get('prices', 'select=*&order=key')

    # 2. New leads (24h) - URL-encode the timestamp
    lead_params = f'select=*&created_at=gte.{quote(yesterday)}&order=created_at.desc'
    new_leads = sb_get('leads', lead_params)

    # 3. All parcels for summary
    parcels = sb_get('parcels', 'select=*')

    # 4. Pending parcels
    pending = [p for p in parcels if p.get('status') in ('pending','delivered','weighed')]

    # Stats
    all_leads = sb_get('leads', 'select=id')
    total_leads = len(all_leads)
    settled = [p for p in parcels if p.get('status') == 'settled']
    total_kg = sum(float(p.get('actual_kg') or 0) for p in settled)
    total_comm = sum(float(p.get('commission_total') or 0) for p in settled)

    # Status breakdown
    status_counts = {}
    for p in parcels:
        s = p.get('status', 'unknown')
        if s not in status_counts: status_counts[s] = {'count': 0, 'kg': 0}
        status_counts[s]['count'] += 1
        status_counts[s]['kg'] += float(p.get('actual_kg') or p.get('estimated_kg') or 0)

    # Build HTML email
    price_rows = ''
    for p in prices:
        price_rows += f"""<tr>
            <td style="padding:8px;border-bottom:1px solid #eee;font-weight:600">{p.get('name_en','')}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(p.get('teaser_thb'))}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(p.get('tier_under20'))}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(p.get('tier_mid'))}</td>
            <td style="padding:8px;border-bottom:1px solid #eee;text-align:right">{fmt_baht(p.get('tier_over50'))}</td>
        </tr>"""

    lead_section = ''
    if new_leads:
        lead_items = ''
        for l in new_leads[:10]:
            lead_items += f"<li><b>{l.get('display_name','?')}</b> - {l.get('material_type','')} ({l.get('weight_kg','?')}kg) via {l.get('source','')}</li>"
        lead_section = f"<h3 style='color:#27ae60'>New Leads: {len(new_leads)}</h3><ul>{lead_items}</ul>"
    else:
        lead_section = "<p style='color:#999'>No new leads in the last 24 hours.</p>"

    status_section = ''
    for s, d in sorted(status_counts.items()):
        status_section += f"<tr><td style='padding:6px 8px;border-bottom:1px solid #eee;text-transform:capitalize'>{s}</td><td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:center'>{d['count']}</td><td style='padding:6px 8px;border-bottom:1px solid #eee;text-align:right'>{d['kg']:.1f} kg</td></tr>"

    pending_section = ''
    if pending:
        for p in pending:
            pending_section += f"<li><b>{p.get('seller_name','?')}</b> - {p.get('material_type','')} ({p.get('estimated_kg','?')}kg) - Status: {p.get('status','')} - Added: {str(p.get('created_at',''))[:10]}</li>"
        pending_section = f"<h3>Pending Actions ({len(pending)})</h3><ul>{pending_section}</ul>"

    html = f"""<html><body style="font-family:-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#333">
    <div style="background:#1a1a2e;color:#fff;padding:20px;border-radius:8px 8px 0 0">
        <h1 style="margin:0;font-size:22px">Thai<span style="color:#27ae60">Carbide</span> Daily Report</h1>
        <p style="margin:4px 0 0;color:#bdc3c7;font-size:13px">{now.strftime('%A, %d %B %Y - %H:%M')} (Bangkok)</p>
    </div>
    <div style="background:#fff;border:1px solid #e0e0e0;border-top:none;padding:20px;border-radius:0 0 8px 8px">

    <div style="display:flex;gap:12px;margin-bottom:20px">
        <div style="flex:1;background:#eafaf1;border-radius:6px;padding:12px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Total Leads</div>
            <div style="font-size:24px;font-weight:700;color:#27ae60">{total_leads}</div>
        </div>
        <div style="flex:1;background:#ebf5fb;border-radius:6px;padding:12px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Settled kg</div>
            <div style="font-size:24px;font-weight:700;color:#2980b9">{total_kg:.1f}</div>
        </div>
        <div style="flex:1;background:#fef9e7;border-radius:6px;padding:12px;text-align:center">
            <div style="font-size:11px;color:#666;text-transform:uppercase">Commission</div>
            <div style="font-size:24px;font-weight:700;color:#d68910">{fmt_baht(total_comm)}</div>
        </div>
    </div>

    <h3>Current Prices</h3>
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

    # Send email
    if not GMAIL_PWD:
        print("GMAIL_APP_PASSWORD not set - printing report to stdout")
        print(html)
        return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"ThaiCarbide Daily Report - {now.strftime('%d %b %Y')}"
    msg['From'] = f"ThaiCarbide Report <{GMAIL_USER}>"
    msg['To'] = REPORT_TO
    msg.attach(MIMEText(html, 'html'))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx) as s:
        s.login(GMAIL_USER, GMAIL_PWD)
        s.sendmail(GMAIL_USER, REPORT_TO, msg.as_string())
    print(f"Report sent to {REPORT_TO}")

if __name__ == '__main__':
    main()
