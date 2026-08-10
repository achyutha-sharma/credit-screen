# Credit ratios from SEC filings

Search a company by name or ticker, get five credit ratios across the last three
fiscal years, colour-coded, pulled directly from SEC's XBRL structured data. No
filing text is parsed and no market data feed is required.

| Ratio | Reads | Strong | Weak |
|---|---|---|---|
| Return on equity | Profitability | above 15% | below 5% |
| Current ratio | Short-term liquidity | above 1.5x | below 1.0x |
| Debt / equity | Balance sheet leverage | below 1.0x | above 2.0x |
| Interest coverage | Ability to service interest | above 4x | below 2x |
| Debt / EBITDA | Leverage against cash earnings | below 2.5x | above 4.0x |

Price-to-earnings is deliberately absent. It prices equity; it says nothing about
whether a borrower can repay.

The thresholds are broad corporate rules of thumb, not standards. Normal leverage
varies widely by industry, so a colour is a prompt to look closer rather than a
verdict. Ratios that are suppressed as not meaningful get no colour at all.

## What this handles that a naive version does not

The arithmetic is trivial. Getting correct inputs out of real filings is not.

**Negative equity.** Sustained buybacks can push stockholders' equity below zero.
ROE and D/E then produce large negative numbers that look like data rather than
nonsense. Both are suppressed and labelled, with a pointer to Debt/EBITDA.

**Unclassified balance sheets.** Banks and insurers do not split current from
non-current assets, so `AssetsCurrent` is simply absent. The current ratio is
marked not applicable rather than shown as zero or missing.

**Interest reported net.** Many filers tag `InterestIncomeExpenseNet` instead of
gross `InterestExpense`. Netting interest income against expense shrinks the
denominator and inflates coverage, sometimes several-fold for cash-rich issuers.
The tool prefers gross tags, falls back only when it must, and flags the result.

**Quarterly figures inside annual filings.** A 10-K carries both annual and
quarterly durations for the same tag. Filtering on form alone silently picks up
a single quarter. Durations are checked to be roughly twelve months.

**Restatements.** The same fiscal year appears across several filings with
different values. Facts are deduplicated by period end, keeping the most
recently filed figure.

**Tag variation.** Companies tag identical line items differently. Each metric
resolves through an ordered chain — depreciation alone has three common variants
— and total debt is summed from separate components rather than read from any
single tag.

**Operating leases.** Where lease liabilities are tagged, a lease-adjusted
Debt/EBITDA is shown alongside the unadjusted figure, matching how rating
agencies treat them. The gap is wide for retailers and airlines.

## The assistant

A chat panel under the ratios answers questions about the company on screen.

The design constraint is the whole point: **the model may only use the figures
the tool extracted.** Every question is sent with a context block containing the
ratios, the ten raw inputs, which XBRL tag produced each one, which were derived
or hand-entered, and the thresholds behind the colours. The system prompt forbids
stating any figure not in that block, forbids estimating a missing value, and
requires it to name what is missing instead.

Without that, an unconstrained model asked "how levered is this company" will
produce a confident number from training data that may be years stale, and the
user cannot tell it apart from the filed figure. Grounding it in the extracted
table is what makes the answers auditable against the table above them.

It also declines investment advice — the framing is credit analysis throughout:
can this borrower service and repay its debt.

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-5"   # optional
```

Everything else in the tool runs without a key; only the chat panel is disabled.
Starter questions are generated from what is actually unusual about the company —
negative equity prompts a different opener than an unclassified balance sheet.

`build_context()` and `suggested_questions()` are covered by the offline tests,
so the part that matters can be verified without spending a token.

## Manual entry

Tag coverage is uneven, and no fallback chain covers every filer. Rather than
dead-ending on a missing figure, every ratio is computed from ten named inputs,
each of which can be typed in by hand:

net income · stockholders' equity · current assets · current liabilities ·
total liabilities · operating income · depreciation & amortisation ·
interest expense · total debt · operating lease liabilities

Extraction and computation are separate steps, so overrides are just a
substitution between them:

```python
from sec_ratios import extract, apply_overrides, compute

a = extract(payload)
a = apply_overrides(a, {"2024-12-31": {"da": 150_000_000, "interest": 75_000_000}})
a = compute(a)
```

Fields not supplied keep their filed values. Passing `None` clears a field, so a
wrongly-tagged figure can be removed as well as replaced. Unknown field names
raise rather than being ignored.

Provenance is preserved throughout: `year.sources` records the XBRL tag behind
each figure, or marks it derived or hand-entered, and any year using manual
input carries a flag naming the fields. A number typed in by an analyst is never
presented as though it came out of the filing.

## Running it

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your.email@example.com"
streamlit run app.py
```

SEC requires a User-Agent identifying the caller and rate-limits to about ten
requests per second. Responses are cached to disk, so repeat lookups do not hit
the API.

To check the logic without a network connection:

```bash
python3 test_offline.py
```

This runs three synthetic filings — a healthy industrial, a negative-equity
retailer, and a bank — through the full pipeline and asserts the expected
output, including the quarterly-contamination and restatement cases.

## Method notes

Ratios use ending balance sheet values rather than period averages; averaging
would be more precise for ROE but obscures the year-over-year comparison.
Debt is long-term debt plus current maturities plus short-term borrowings.
EBITDA is operating income plus depreciation and amortisation. Where total
liabilities are untagged, they are derived as assets less equity and flagged.

## Files

- `sec_ratios.py` — fetching, tag resolution, ratios, guard clauses
- `app.py` — Streamlit interface
- `test_offline.py` — synthetic-filing checks
