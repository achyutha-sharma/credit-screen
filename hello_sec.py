"""
Step 1. The smallest thing that proves the pipeline is possible.

Ticker in, CIK out, then one real number off a real filing. Nothing else.
Run this before writing anything larger -- if it works, the rest of the
project is just doing more of the same.

    python3 hello_sec.py NKE
"""

import os
import sys

import requests

UA = os.environ.get("SEC_USER_AGENT")
if not UA:
    sys.exit(
        'Set your contact details first, e.g.\n'
        '  export SEC_USER_AGENT="Your Name you@email.com"\n'
        "SEC rejects requests that do not say who is calling."
    )

ticker = (sys.argv[1] if len(sys.argv) > 1 else "NKE").upper()
headers = {"User-Agent": UA}

# --- 1. ticker -> CIK -----------------------------------------------------
# SEC indexes by CIK, not ticker. This file maps one to the other.
print(f"Looking up {ticker}...")
tickers = requests.get(
    "https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=30
).json()

match = next((r for r in tickers.values() if r["ticker"].upper() == ticker), None)
if not match:
    sys.exit(f"No SEC filer with ticker {ticker}.")

cik = str(match["cik_str"]).zfill(10)  # must be 10 digits, zero-padded
print(f"  {match['title']}  CIK {cik}")

# --- 2. CIK -> every tagged number the company has ever filed -------------
print("Fetching company facts (a few MB)...")
facts = requests.get(
    f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", headers=headers, timeout=60
).json()

gaap = facts["facts"]["us-gaap"]
print(f"  {len(gaap):,} different tags available for this company")

# --- 3. Look at one tag, raw ---------------------------------------------
# This is the part worth staring at. Every quirk the real code handles is
# visible here: quarterly rows mixed with annual, the same period repeated
# across filings, 'start' present on income items and absent on balance ones.
print("\nRaw NetIncomeLoss entries from 10-K filings (newest 6):")
rows = [e for e in gaap["NetIncomeLoss"]["units"]["USD"] if e.get("form", "").startswith("10-K")]
rows.sort(key=lambda e: (e["end"], e.get("filed", "")), reverse=True)

print(f"  {'start':<12}{'end':<12}{'filed':<12}{'value':>18}")
for e in rows[:6]:
    span = ""
    if e.get("start"):
        from datetime import date

        d = lambda s: date(*map(int, s.split("-")))
        span = f"  ({(d(e['end']) - d(e['start'])).days}d)"
    print(
        f"  {e.get('start','--'):<12}{e['end']:<12}{e.get('filed','?'):<12}"
        f"{e['val']:>18,.0f}{span}"
    )

print(
    "\nNotice: some spans are ~365 days and some are ~90. Some period ends appear\n"
    "twice with different filed dates and different values. Filtering that mess\n"
    "correctly is the actual work -- sec_ratios.py does it."
)
