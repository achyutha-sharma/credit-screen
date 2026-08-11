"""
Streamlit front end.

Search a company, pull its filings, show colour-coded ratios, offer manual
entry for anything untagged, and explain what each ratio means in plain words.

Run with: streamlit run app.py
"""

import html
import os

import streamlit as st

import assistant
from sec_ratios import (
    GOOD,
    RATIO_DIRECTION,
    Analysis,
    compare,
    INPUT_FIELDS,
    MANUAL,
    MISSING,
    RATIO_GROUPS,
    RATIO_ORDER,
    WATCH,
    WEAK,
    SecClient,
    apply_overrides,
    compute,
    extract,
    grade,
)

st.set_page_config(page_title="Credit Screen", layout="centered")

HISTORY_YEARS = 10   # fetched, and drawn in the sparklines
SHOWN_YEARS = 3      # columns in the table

# --------------------------------------------------------------------------
# Look
# --------------------------------------------------------------------------
# Ink, paper and one teal accent. Every other colour is reserved for the ratio
# cells, because there the colour *is* the information -- spending it on
# decoration would dilute the only place it carries meaning.

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root{
  --ink:#131C24; --ink-2:#4A5A66; --ink-3:#8595A0;
  --rule:#D9E0E4; --rule-2:#EBEFF1; --card:#FFFFFF; --paper:#E4E5E6;
  --accent:#10495B; --accent-soft:#E4EEF1;
  --good-fg:#216B48; --good-bg:#DDEBE2; --good-bar:#4E9670;
  --watch-fg:#83600F; --watch-bg:#F6ECD0; --watch-bar:#C69A2E;
  --weak-fg:#9C3535; --weak-bg:#F4DEDE; --weak-bar:#C06666;
  --mono:'IBM Plex Mono',ui-monospace,Menlo,monospace;
}
html, body, [class*="css"], .stApp{
  font-family:'Archivo',system-ui,-apple-system,sans-serif; color:var(--ink);
}
.stApp{background:var(--paper)}
.block-container{
  max-width:920px; background:var(--card); border:1px solid var(--rule);
  border-radius:6px; padding:2.6rem 2.6rem 3.2rem; margin-top:3.2rem;
  margin-bottom:3rem; box-shadow:0 1px 2px rgba(19,28,36,.05),
  0 8px 24px -12px rgba(19,28,36,.10);
}
/* Tables sit on the card, so they carry a rule rather than their own fill. */
.matrix, .extable{background:transparent}
@media (max-width:720px){
  /* Streamlit pins a toolbar to the top on mobile; without room for it the
     masthead sits underneath and is clipped. */
  .block-container{padding:1.6rem 1.1rem 2.2rem; border-radius:0;
    border-left:0; border-right:0; margin-top:3.4rem; margin-bottom:0}
  .mark{font-size:1.15rem}
}

/* masthead */
.mark{font-size:1.3rem;font-weight:700;letter-spacing:-.02em;line-height:1.2}
.mark span{color:var(--accent)}
.tag{font-size:.68rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;margin-top:.15rem}
.rule{border-bottom:2px solid var(--ink);margin:.7rem 0 1.1rem}
div[data-testid="stPopover"] button{border:1px solid var(--rule);
  background:var(--card);color:var(--ink-2);font-size:.78rem;font-weight:600;
  border-radius:3px;padding:.3rem .7rem}
div[data-testid="stPopover"] button:hover{border-color:var(--accent);
  color:var(--accent)}
.lede{color:var(--ink-2);font-size:.95rem;max-width:62ch;margin:0 0 .4rem}

/* company head */
.co{margin:1.9rem 0 .2rem}
.co h2{margin:0;font-size:1.65rem;font-weight:700;letter-spacing:-.02em}
.co .meta{display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:.3rem;
  font-family:var(--mono);font-size:.72rem;color:var(--ink-3)}

/* the ratio matrix -- the one place colour is spent */
.matrix{margin-top:1rem;border:1px solid var(--rule);border-radius:3px;
  overflow-x:auto;background:var(--card)}
.matrix table{width:100%;border-collapse:collapse}
.matrix th{font-size:.66rem;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;padding:.8rem .9rem;text-align:right;
  border-bottom:1px solid var(--rule);white-space:nowrap}
.matrix th:first-child{text-align:left}
.matrix tr{border-bottom:1px solid var(--rule-2)}
.matrix tr:last-child{border-bottom:0}
.matrix tr.grp td{background:#F4F7F8;padding:.4rem .9rem;font-size:.63rem;
  letter-spacing:.14em;text-transform:uppercase;color:var(--accent);
  font-weight:700;border-top:1px solid var(--rule)}
.matrix tr.grp:first-child td{border-top:0}
.matrix td{padding:.45rem .5rem;vertical-align:middle}
.matrix td.rname{padding:.7rem .9rem;min-width:180px}
.rname b{display:block;font-weight:600;font-size:.92rem}
.rname i{display:block;font-style:normal;font-size:.68rem;color:var(--ink-3);
  font-family:var(--mono);margin-top:.1rem}
.cell{display:block;position:relative;padding:.45rem .65rem .45rem 1rem;
  border-radius:2px;font-family:var(--mono);font-size:.98rem;font-weight:500;
  font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.cell::before{content:"";position:absolute;left:.3rem;top:.4rem;bottom:.4rem;
  width:3px;border-radius:2px}
.cell.good{background:var(--good-bg);color:var(--good-fg)}
.cell.good::before{background:var(--good-bar)}
.cell.watch{background:var(--watch-bg);color:var(--watch-fg)}
.cell.watch::before{background:var(--watch-bar)}
.cell.weak{background:var(--weak-bg);color:var(--weak-fg)}
.cell.weak::before{background:var(--weak-bar)}
/* Not meaningful is a third state, never a bad score: never filled. */
.cell.none{background:transparent;color:var(--ink-3);font-size:.73rem;
  border:1px dashed var(--rule);padding-left:.65rem;white-space:normal;
  font-weight:400}
.cell.none::before{display:none}

.legend{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;
  margin:.7rem 0 0;font-size:.78rem;color:var(--ink-2)}
.chip{font-family:var(--mono);font-size:.66rem;font-weight:600;
  letter-spacing:.06em;text-transform:uppercase;padding:.2rem .5rem;border-radius:2px}
.chip.good{background:var(--good-bg);color:var(--good-fg)}
.chip.watch{background:var(--watch-bg);color:var(--watch-fg)}
.chip.weak{background:var(--weak-bg);color:var(--weak-fg)}
.chip.none{border:1px dashed var(--rule);color:var(--ink-3)}

/* notes */
.notes{margin-top:1.3rem}
.notes h3, .explain h3{font-size:.68rem;letter-spacing:.13em;
  text-transform:uppercase;color:var(--ink-3);font-weight:600;margin:0 0 .5rem}
.notes p{position:relative;padding:.5rem 0 .5rem 1.3rem;margin:0;
  font-size:.87rem;color:var(--ink-2);border-bottom:1px solid var(--rule-2)}
.notes p:last-child{border-bottom:0}
.notes p::before{content:"";position:absolute;left:.3rem;top:1.05em;
  width:5px;height:5px;border-radius:50%;background:var(--ink-3)}

/* plain-English explanations */
.explain{margin-top:2rem;padding-top:1.4rem;border-top:2px solid var(--ink)}
.extable{border:1px solid var(--rule);border-radius:3px;overflow-x:auto;
  background:var(--card)}
.extable table{width:100%;border-collapse:collapse}
.extable th{font-size:.64rem;letter-spacing:.12em;text-transform:uppercase;
  color:var(--ink-3);font-weight:600;padding:.75rem .85rem;text-align:left;
  border-bottom:1px solid var(--rule);vertical-align:bottom}
.extable tr{border-bottom:1px solid var(--rule-2)}
.extable tr:last-child{border-bottom:0}
.extable td{padding:.8rem .85rem;vertical-align:top;font-size:.87rem}
td.rx{min-width:150px}
td.rx b{display:block;font-weight:700;font-size:.92rem;letter-spacing:-.01em}
td.rx i{display:block;font-style:normal;font-family:var(--mono);font-size:.64rem;
  color:var(--ink-3);margin-top:.2rem;line-height:1.4}
td.mx{color:var(--ink-2);min-width:180px}
td.sx{color:var(--ink);min-width:230px}
td.sx b{font-family:var(--mono);font-weight:600;color:var(--accent)}

/* figures table */
.figs{width:100%;border-collapse:collapse;font-size:.83rem}
.figs th{font-size:.64rem;letter-spacing:.11em;text-transform:uppercase;
  color:var(--ink-3);text-align:right;padding:.45rem .55rem;
  border-bottom:1px solid var(--rule)}
.figs th:first-child,.figs th:last-child{text-align:left}
.figs td{padding:.4rem .55rem;text-align:right;font-family:var(--mono);
  font-variant-numeric:tabular-nums;border-bottom:1px solid var(--rule-2)}
.figs td:first-child{text-align:left;font-family:'Archivo',sans-serif}
.figs td.src{text-align:left;font-size:.66rem;color:var(--ink-3)}
.figs td.src.man{color:var(--accent);font-weight:600}
.figs td.src.der{color:var(--watch-fg)}
.figs td.src.gap{color:var(--ink-3);font-style:italic}

/* ---------- motion ---------- */
@keyframes rise{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes draw{to{stroke-dashoffset:0}}

.co, .matrix, .legend, .notes, .explain, .extable{animation:rise .45s cubic-bezier(.22,.8,.3,1) both}
.matrix{animation-delay:.05s}
.legend{animation-delay:.12s}
.notes{animation-delay:.16s}

.matrix tbody tr{animation:fade .34s ease both}
.matrix tbody tr:nth-child(1){animation-delay:.06s}
.matrix tbody tr:nth-child(2){animation-delay:.09s}
.matrix tbody tr:nth-child(3){animation-delay:.12s}
.matrix tbody tr:nth-child(4){animation-delay:.15s}
.matrix tbody tr:nth-child(5){animation-delay:.18s}
.matrix tbody tr:nth-child(6){animation-delay:.21s}
.matrix tbody tr:nth-child(7){animation-delay:.24s}
.matrix tbody tr:nth-child(8){animation-delay:.27s}
.matrix tbody tr:nth-child(9){animation-delay:.30s}
.matrix tbody tr:nth-child(10){animation-delay:.33s}
.matrix tbody tr:nth-child(11){animation-delay:.36s}
.matrix tbody tr:nth-child(12){animation-delay:.39s}
.matrix tbody tr:nth-child(n+13){animation-delay:.42s}

/* The trend line traces itself, so the eye follows the direction of travel. */
.spark polyline{stroke-dasharray:260;stroke-dashoffset:260;
  animation:draw 1.15s cubic-bezier(.3,.9,.3,1) .3s forwards}
.spark circle{opacity:0;animation:fade .35s ease 1.25s forwards}

.matrix tbody tr:not(.grp){transition:background .16s ease}
.matrix tbody tr:not(.grp):hover{background:#F7FAFB}
.cell, .pc{transition:filter .16s ease}
.matrix tbody tr:hover .cell{filter:saturate(1.25)}

@media (prefers-reduced-motion:reduce){
  *{animation:none !important; transition:none !important}
  .spark polyline{stroke-dashoffset:0}
  .spark circle{opacity:1}
}

/* streamlit widget tuning */
.stTextInput input, .stNumberInput input{font-family:var(--mono)}
.stButton button{border-radius:3px}
div[data-testid="stExpander"]{border-color:var(--rule)}

.matrix th .per{font-family:var(--mono);font-size:.6rem;color:var(--ink-3);
  font-weight:400;letter-spacing:0;text-transform:none}
.pc{display:block;padding:.45rem .65rem;border-radius:2px;font-family:var(--mono);
  font-size:.95rem;font-variant-numeric:tabular-nums;text-align:right;
  white-space:nowrap;font-weight:500}
.pc.better{background:var(--good-bg);color:var(--good-fg)}
.pc.worse{background:var(--weak-bg);color:var(--weak-fg)}
.pc.in-line,.pc.flat{background:transparent;color:var(--ink-2)}
td.trend, th.trend{text-align:right;padding:.35rem .8rem .35rem .5rem;
  border-left:1px solid var(--rule-2);width:1%;white-space:nowrap}
th.trend{font-size:.6rem}
.spark{display:block;overflow:visible;opacity:.85}
tr:hover .spark{opacity:1}
td.med{text-align:right;font-family:var(--mono);font-size:.85rem;
  color:var(--ink-3);padding:.45rem .9rem;border-left:1px solid var(--rule)}
.chip.better{background:var(--good-bg);color:var(--good-fg)}
.chip.worse{background:var(--weak-bg);color:var(--weak-fg)}
.chip.flat{border:1px solid var(--rule);color:var(--ink-2)}
</style>
""",
    unsafe_allow_html=True,
)

E = html.escape

ABOUT = """
#### What this does differently

**It says what each number means.** Most tools show you `1.30x` and stop. Here
every ratio comes with a sentence built from the company's own figures — *for
every $1 the owners have in, the company owes $1.30 to others.*

**It refuses to mislead you.** Some ratios are meaningless for some companies,
and printing them anyway is worse than leaving them out.

- A bank has no current ratio and does not report EBITDA. Interest paid to
  depositors is the cost of the product, not a financing charge, so those rows
  are left unscored rather than filled with a number that looks fine.
- Home Depot has bought back so much stock that the owners' stake is nearly
  zero. Return on equity comes out above 1,000% — arithmetically true, and
  useless. The figure is shown but never graded.
- Asset turnover is never scored at all. A power utility runs near 0.3 and a
  supermarket near 3.0, both perfectly healthy, so any universal threshold
  would just report the industry back to you as a verdict.

**It shows its work.** Every figure names the label the company filed it under.
Anything rebuilt from other figures is marked as rebuilt, and anything you
typed in yourself is flagged as yours. A number you entered is never presented
as though the company filed it.

**Nothing is quietly invented.** Where a label is missing the tool tries a list
of alternatives, then tries to reconstruct the figure from others, then asks
you. Each step is visible in the source column.

**Peers instead of arbitrary lines.** Comparing against two or three real
competitors scores a margin or a turnover honestly, because the industry
cancels out — no invented benchmark required.

---

Data comes straight from the SEC's structured filing data. No third-party
feeds, nothing scraped, nothing estimated. US filers only, annual reports only.

A screening tool, not an analysis — it tells you where to look. The filing
tells you what is actually going on.
"""


_mast, _about = st.columns([5, 1], vertical_alignment="bottom")
with _mast:
    st.markdown(
        '<div class="mark">Credit<span>Screen</span></div>'
        '<div class="tag">Ratios from SEC filings</div>',
        unsafe_allow_html=True,
    )
with _about:
    with st.popover("About"):
        st.markdown(ABOUT)
st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
st.markdown(
    '<p class="lede">Type a company name to pull its last three annual reports '
    "and work out whether it can service what it owes.</p>",
    unsafe_allow_html=True,
)

user_agent = os.environ.get("SEC_USER_AGENT")
if not user_agent:
    st.error(
        "Set SEC_USER_AGENT to your name and email before running. "
        "The SEC turns away requests that do not identify the caller."
    )
    st.stop()

client = SecClient(user_agent=user_agent)


@st.cache_data(show_spinner=False)
def search(query: str) -> list[dict]:
    return client.search(query)


@st.cache_data(show_spinner=False)
def fetch(cik: str) -> dict:
    """Only the raw payload is cached, never the analysis."""
    return client.company_facts(cik)


@st.cache_data(show_spinner=False)
def profile(cik: str) -> dict:
    """Registration details, including the SEC's industry code. Never raises."""
    return client.company_profile(cik)


# --------------------------------------------------------------------------
# 1. Find the company
# --------------------------------------------------------------------------

query = st.text_input("Company name or ticker", placeholder="Home Depot").strip()

if not query:
    st.caption("Try Home Depot, Nike, or JPMorgan.")
    st.stop()

try:
    matches = search(query)
except Exception as e:
    st.error(f"Could not reach the SEC: {e}")
    st.stop()

if not matches:
    st.warning(
        f"Nothing matches “{query}”. Only US companies that file with the SEC "
        "are covered — try a shorter name, or the ticker."
    )
    st.stop()

if len(matches) == 1:
    chosen = matches[0]
    st.caption(f"Matched {chosen['name']} ({chosen['ticker']})")
else:
    # Shown whenever there is more than one candidate, so a near-miss on the
    # name is one click from the right filer rather than a retyped search.
    chosen = st.selectbox(
        "Did you mean",
        matches,
        format_func=lambda m: f"{m['name']} · {m['ticker']}",
        label_visibility="collapsed",
    )

# --------------------------------------------------------------------------
# 2. Pull the filings
# --------------------------------------------------------------------------

try:
    with st.spinner(f"Fetching {chosen['ticker']} filings"):
        payload = fetch(chosen["cik"])
    # Pull a decade, show three. The extra years cost nothing -- they are
    # already in the payload we downloaded -- and they give the sparklines
    # something worth tracing. A twelve-column table would be unreadable.
    base = extract(payload, years=HISTORY_YEARS)
except ValueError as e:
    st.warning(str(e))
    st.stop()
except Exception as e:
    st.error(f"Could not load filings: {e}")
    st.stop()

years = sorted(base.years, key=lambda y: y.period_end)[-SHOWN_YEARS:]


def widget_key(year_key: str, field_key: str) -> str:
    return f"{chosen['cik']}|{year_key}|{field_key}"


# --------------------------------------------------------------------------
# 3. Manual entry for anything untagged
# --------------------------------------------------------------------------

prefill = {
    y.key: {
        f.key: (None if y.inputs.get(f.key) is None else float(round(y.inputs[f.key] / 1e6)))
        for f in INPUT_FIELDS
    }
    for y in years
}

gaps = sum(len(y.missing()) for y in years)

with st.expander(
    f"Fill in or correct figures — {gaps} not found" if gaps else "Fill in or correct figures",
    expanded=False,
):
    st.caption(
        "All figures in $ millions. A blank field means the filing did not tag it — "
        "type it off the statement and the ratios update. Clearing a field removes it."
    )
    if st.button("Reset to filed figures"):
        for y in years:
            for f in INPUT_FIELDS:
                st.session_state.pop(widget_key(y.key, f.key), None)
        st.rerun()

    for tab, y in zip(st.tabs([y.label for y in years]), years):
        with tab:
            for f in INPUT_FIELDS:
                src = y.sources.get(f.key, MISSING)
                st.number_input(
                    f.label,
                    value=prefill[y.key][f.key],
                    key=widget_key(y.key, f.key),
                    step=1.0,
                    format="%.0f",
                    help=f"{f.hint} · "
                    + ("not found, enter manually" if src == MISSING else src),
                )

overrides = {}
for y in years:
    changed = {
        f.key: (None if st.session_state.get(widget_key(y.key, f.key)) is None
                else float(st.session_state[widget_key(y.key, f.key)]) * 1e6)
        for f in INPUT_FIELDS
        if st.session_state.get(widget_key(y.key, f.key)) != prefill[y.key][f.key]
    }
    if changed:
        overrides[y.key] = changed

full = compute(apply_overrides(base, overrides))
history = sorted(full.years, key=lambda y: y.period_end)
ordered = history[-SHOWN_YEARS:]

# Everything downstream -- ratios, explanations, peers, the assistant -- reads
# the recent window. Only the sparklines use the full decade, so a long history
# never bloats the table or the context sent to the model.
result = Analysis(entity=full.entity, years=ordered, is_financial=full.is_financial)

# --------------------------------------------------------------------------
# 4. The ratio matrix
# --------------------------------------------------------------------------

MEANING = {
    "Current ratio": "bills due this year",
    "Quick ratio": "same, minus inventory",
    "Debt / equity": "borrowed vs owners' money",
    "Debt / assets": "share of assets funded by debt",
    "Debt / EBITDA": "years of earnings to repay",
    "Debt / EBITDA (lease-adj.)": "same, counting leases",
    "Interest coverage": "can it pay the interest",
    "Net profit margin": "profit per dollar of sales",
    "EBITDA margin": "operating profit per dollar of sales",
    "Return on assets": "profit per dollar of assets",
    "Return on equity": "profit per dollar of owner money",
    "Asset turnover": "sales per dollar of assets",
}
DIRECTION = {
    "Current ratio": "↑", "Quick ratio": "↑", "Interest coverage": "↑",
    "Net profit margin": "↑", "EBITDA margin": "↑",
    "Return on assets": "↑", "Return on equity": "↑",
    "Debt / equity": "↓", "Debt / assets": "↓",
    "Debt / EBITDA": "↓", "Debt / EBITDA (lease-adj.)": "↓",
    "Asset turnover": "",
}

st.markdown(
    f'<div class="co"><h2>{E(result.entity)}</h2><div class="meta">'
    + "".join(
        f"<span>{E(t)}</span>"
        for t in filter(None, (
            chosen["ticker"],
            f"CIK {chosen['cik']}",
            f"{ordered[0].label}–{ordered[-1].label}",
            (lambda p: f"SIC {p['sic']} · {p['industry']}" if p.get("sic") else None)(
                profile(chosen["cik"])),
        ))
    )
    + "</div></div>",
    unsafe_allow_html=True,
)

rows_present = [r for r in RATIO_ORDER if any(r in y.ratios for y in ordered)]
span = len(ordered) + 2


def sparkline(name: str, points: list, width: int = 76, height: int = 22) -> str:
    """Inline SVG trend across every year we have, not just the three shown.

    Drawn on its own scale, so it reports shape rather than level -- the level
    is already in the cells beside it. Fewer than three usable points earns no
    chart, because two dots joined by a line is a shape the data does not
    support.
    """
    vals = [(i, y.values.get(name)) for i, y in enumerate(points)]
    usable = [(i, v) for i, v in vals if v is not None]
    if len(usable) < 3:
        return ""

    lo = min(v for _, v in usable)
    hi = max(v for _, v in usable)
    rng = (hi - lo) or 1.0
    last_i = len(points) - 1

    def xy(i: int, v: float) -> tuple[float, float]:
        x = 1 + (i / max(last_i, 1)) * (width - 2)
        y = height - 3 - ((v - lo) / rng) * (height - 6)
        return round(x, 1), round(y, 1)

    pts = " ".join(f"{x},{y}" for x, y in (xy(i, v) for i, v in usable))
    fx, fy = xy(*usable[-1])
    good = grade(name, usable[-1][1])
    dot = {"good": "var(--good-bar)", "watch": "var(--watch-bar)",
           "weak": "var(--weak-bar)"}.get(good, "var(--ink-3)")
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" '
        f'height="{height}" aria-hidden="true">'
        f'<polyline points="{pts}" fill="none" stroke="var(--ink-3)" '
        f'stroke-width="1.25" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{fx}" cy="{fy}" r="2.1" fill="{dot}"/></svg>'
    )


body = ""
for group, names in RATIO_GROUPS:
    shown = [n for n in names if n in rows_present]
    if not shown:
        continue
    body += f'<tr class="grp"><td colspan="{span}">{E(group)}</td></tr>'
    for name in shown:
        cells = ""
        for y in ordered:
            bucket = grade(name, y.values.get(name))
            text = y.ratios.get(name, MISSING)
            cells += f'<td><span class="cell {bucket or "none"}">{E(text)}</span></td>'
        body += (
            f'<tr><td class="rname"><b>{E(name)}</b>'
            f'<i>{DIRECTION.get(name, "")} {E(MEANING.get(name, ""))}</i></td>{cells}'
            f'<td class="trend">{sparkline(name, history)}</td></tr>'
        )

st.markdown(
    '<div class="matrix"><table><thead><tr><th>Ratio</th>'
    + "".join(f"<th>{E(y.label)}</th>" for y in ordered)
    + f'<th class="trend">{len(history)}-yr trend</th>'
    + f"</tr></thead><tbody>{body}</tbody></table></div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="legend"><span class="chip good">strong</span>'
    '<span class="chip watch">watch</span><span class="chip weak">weak</span>'
    '<span class="chip none">n/m</span>'
    "<span>&nbsp;“n/m” means the ratio does not apply here — a different thing "
    "from a bad score, so it is left uncoloured.</span></div>",
    unsafe_allow_html=True,
)

if result.all_flags:
    st.markdown(
        '<div class="notes"><h3>Worth knowing</h3>'
        + "".join(f"<p>{E(f)}</p>" for f in result.all_flags)
        + "</div>",
        unsafe_allow_html=True,
    )

# --------------------------------------------------------------------------
# 5. The underlying figures
# --------------------------------------------------------------------------

with st.expander("Where these numbers came from"):
    latest = ordered[-1]
    rows = ""
    for f in INPUT_FIELDS:
        cells = "".join(
            f"<td>{'—' if y.inputs.get(f.key) is None else f'{y.inputs[f.key] / 1e6:,.0f}'}</td>"
            for y in ordered
        )
        src = latest.sources.get(f.key, MISSING)
        cls = ("man" if src == MANUAL else "der" if src.startswith("derived")
               else "gap" if src == MISSING else "")
        label = ("you entered this" if src == MANUAL else src)
        rows += f'<tr><td>{E(f.label)}</td>{cells}<td class="src {cls}">{E(label)}</td></tr>'
    st.markdown(
        '<table class="figs"><thead><tr><th>Figure</th>'
        + "".join(f"<th>{E(y.label)}</th>" for y in ordered)
        + "<th>Source, latest year</th></tr></thead>"
        + f"<tbody>{rows}</tbody></table>",
        unsafe_allow_html=True,
    )
    st.caption(
        "$ millions. A source name is the label the company filed the figure under. "
        "“derived” means the tool rebuilt it from other figures; those are worth "
        "checking against the report."
    )

# --------------------------------------------------------------------------
# 6. Peers
# --------------------------------------------------------------------------
# Absolute thresholds cannot honestly score a margin or an asset turnover --
# what counts as good depends on the industry. A peer set answers the same
# question without inventing a band, because the industry cancels out.

st.markdown('<div class="explain"><h3>Compare with peers</h3></div>', unsafe_allow_html=True)

subject_profile = profile(chosen["cik"])
if subject_profile.get("industry"):
    st.caption(
        f"The SEC classifies this filer as **{subject_profile['industry']}** "
        f"(SIC {subject_profile['sic']}). Companies with the same code are the "
        "ones worth comparing against."
    )

peer_query = st.text_input(
    "Peer companies",
    placeholder="Lowes, Target",
    help="Names or tickers, separated by commas. Two or three works best.",
    label_visibility="collapsed",
)

if peer_query.strip():
    wanted = [p.strip() for p in peer_query.split(",") if p.strip()][:4]
    peers, unresolved, off_industry = [], [], []
    for term in wanted:
        hits = search(term)
        if not hits or hits[0]["cik"] == chosen["cik"]:
            unresolved.append(term)
            continue
        try:
            peers.append(compute(extract(fetch(hits[0]["cik"]))))
        except Exception:
            unresolved.append(term)
            continue
        # Different SIC does not make a comparison wrong, but it is worth
        # knowing before reading a margin gap as a performance difference.
        pp = profile(hits[0]["cik"])
        if (
            subject_profile.get("sic")
            and pp.get("sic")
            and pp["sic"] != subject_profile["sic"]
        ):
            off_industry.append(f"{hits[0]['ticker']} is {pp['industry']}")

    if unresolved:
        st.caption("Could not use: " + ", ".join(unresolved))

    if peers:
        comp = compare([result] + peers)
        head = "".join(
            f"<th>{E(n)}<br><span class='per'>{E(p)}</span></th>"
            for n, p in zip(comp.names, comp.periods)
        )
        rows_p = ""
        for group, names in RATIO_GROUPS:
            shown = [r for r in comp.rows if r.ratio in names]
            if not shown:
                continue
            rows_p += f'<tr class="grp"><td colspan="{len(comp.names) + 2}">{E(group)}</td></tr>'
            for row in shown:
                cells = "".join(
                    f'<td><span class="pc {c.standing.replace(" ", "-") if c.standing else "flat"}">'
                    f"{E(c.text)}</span></td>"
                    for c in row.cells
                )
                rows_p += (
                    f'<tr><td class="rname"><b>{E(row.ratio)}</b></td>{cells}'
                    f'<td class="med">{E(row.median_text)}</td></tr>'
                )
        st.markdown(
            f'<div class="matrix"><table><thead><tr><th>Ratio</th>{head}'
            f"<th>Median</th></tr></thead><tbody>{rows_p}</tbody></table></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="legend"><span class="chip better">better</span>'
            '<span class="chip flat">in line</span>'
            '<span class="chip worse">worse</span>'
            "<span>&nbsp;against the median of the companies shown, not a fixed "
            "threshold — so the industry cancels out.</span></div>",
            unsafe_allow_html=True,
        )
        for note in comp.notes:
            st.caption(note)
        if off_industry:
            st.caption(
                "Different SEC industry code: "
                + "; ".join(off_industry)
                + ". Still worth comparing, but a margin gap may be the business "
                "model rather than performance."
            )
    elif not unresolved:
        st.caption("No peers found.")

# --------------------------------------------------------------------------
# 7. What the numbers mean
# --------------------------------------------------------------------------
# The third column is worked from this company's own latest figure, because a
# number you can read as a sentence about a real business is understood far
# faster than a definition.

D = "&#36;"  # Streamlit reads a bare $ as the start of a LaTeX expression.


def reading(name: str, value: float | None, text: str) -> str:
    """One sentence saying what this company's figure actually means."""
    if value is None:
        return f"Not shown here — {E(text.split(' - ')[-1].strip())}. See the notes above."
    if name == "Return on equity":
        return (
            f"For every {D}1 the owners have in the business, it earns "
            f"<b>{D}{value / 100:,.2f} of profit</b> a year."
        )
    if name == "Current ratio":
        return (
            f"For every {D}1 of bills due within the year, there is "
            f"<b>{D}{value:,.2f} on hand</b> to pay them."
        )
    if name == "Quick ratio":
        return (
            f"Excluding stock that still has to be sold, there is "
            f"<b>{D}{value:,.2f}</b> for every {D}1 of bills due this year."
        )
    if name == "Debt / equity":
        return (
            f"For every {D}1 the owners have in, the company owes "
            f"<b>{D}{value:,.2f} to others</b>."
        )
    if name == "Debt / assets":
        return (
            f"<b>{value * 100:,.0f}% of everything the company owns</b> is funded "
            f"by what it owes; the rest belongs to the owners."
        )
    if name == "Net profit margin":
        return (
            f"Every {D}1 of sales leaves <b>{D}{value / 100:,.3f} of profit</b> "
            f"once every cost is paid."
        )
    if name == "EBITDA margin":
        return (
            f"Every {D}1 of sales leaves <b>{D}{value / 100:,.3f}</b> before "
            f"interest, tax and the cost of wearing out its assets."
        )
    if name == "Return on assets":
        return (
            f"Every {D}1 of assets the company owns generates "
            f"<b>{D}{value / 100:,.3f} of profit</b> a year."
        )
    if name == "Asset turnover":
        return (
            f"Every {D}1 of assets produces <b>{D}{value:,.2f} of sales</b> a year. "
            f"Not scored — a power station and a supermarket are nowhere near comparable."
        )
    if name == "Interest coverage":
        room = 100 * (1 - 1 / value) if value > 1 else 0
        return (
            f"Earnings cover the interest bill <b>{value:,.1f} times over</b>. "
            f"Profits could fall about {room:,.0f}% before interest stopped being covered."
        )
    if name.startswith("Debt / EBITDA"):
        what = "the debt including its leases" if "lease" in name else "the debt"
        return (
            f"It would take roughly <b>{value:,.1f} years of earnings</b> to clear "
            f"{what}, if every dollar went to paying it down."
        )
    return ""


MEASURES = [
    ("Current ratio", "Assets due within a year ÷ bills due within a year",
     "Strong above 1.5x · weak below 1.0x"),
    ("Quick ratio", "The same, with inventory taken out of the top",
     "Strong above 1.0x · weak below 0.5x"),
    ("Debt / equity", "Everything owed ÷ the owners’ stake",
     "Strong below 1.0x · weak above 2.0x"),
    ("Debt / assets", "Everything owed ÷ everything owned",
     "Strong below 0.5 · weak above 0.7"),
    ("Debt / EBITDA", "Borrowings ÷ yearly earnings before interest, tax and depreciation",
     "Strong below 2.5x · weak above 4.0x"),
    ("Debt / EBITDA (lease-adj.)", "Borrowings plus leases ÷ those same earnings",
     "Strong below 3.0x · weak above 4.5x"),
    ("Interest coverage", "Operating profit ÷ the annual interest bill",
     "Strong above 4x · weak below 2x"),
    ("Net profit margin", "Profit ÷ sales",
     "Strong above 10% · weak below 3%"),
    ("EBITDA margin", "Earnings before interest, tax and depreciation ÷ sales",
     "Strong above 20% · weak below 8%"),
    ("Return on assets", "Profit ÷ everything owned",
     "Strong above 5% · weak below 1.5%"),
    ("Return on equity", "Profit ÷ the owners’ stake",
     "Strong above 15% · weak below 5%"),
    ("Asset turnover", "Sales ÷ everything owned",
     "Not scored — no universal benchmark"),
]

latest = ordered[-1]
short_name = result.entity.split(",")[0].title()

rows_ex = ""
for name, measure, band in MEASURES:
    if name not in rows_present:
        continue
    says = reading(name, latest.values.get(name), latest.ratios.get(name, ""))
    rows_ex += (
        f'<tr><td class="rx"><b>{E(name)}</b><i>{E(band)}</i></td>'
        f"<td class=\"mx\">{E(measure)}</td><td class=\"sx\">{says}</td></tr>"
    )

st.markdown(
    '<div class="explain"><h3>What these numbers mean</h3>'
    '<div class="extable"><table><thead><tr><th>Ratio</th>'
    "<th>How it is worked out</th>"
    f"<th>What {E(short_name)}’s {E(latest.label)} figure says</th></tr></thead>"
    f"<tbody>{rows_ex}</tbody></table></div></div>",
    unsafe_allow_html=True,
)
st.caption(
    "The thresholds are rough rules of thumb, not standards — what counts as too "
    "much debt depends heavily on the industry. A utility and a software company "
    "are not comparable. Read a colour as a reason to look closer, never a verdict."
)

# --------------------------------------------------------------------------
# 7. Assistant, only when a key is configured
# --------------------------------------------------------------------------

if not assistant.available():
    st.stop()

st.divider()
st.subheader("Ask about these numbers")
st.caption(
    "Answers come only from the figures above. The assistant cannot look anything "
    "up, and will say so when the tool did not find something."
)

thread_key = f"chat_{chosen['cik']}"
history = st.session_state.setdefault(thread_key, [])

pending = None
if not history:
    cols = st.columns(2)
    for n, q in enumerate(assistant.suggested_questions(result)):
        if cols[n % 2].button(q, key=f"sq{n}"):
            pending = q

for turn in history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

question = st.chat_input("e.g. is this much debt a problem for a retailer?") or pending

if question:
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            with st.spinner("Reading the figures"):
                answer = assistant.ask(
                    result, question, history=history,
                    ticker=chosen["ticker"], cik=chosen["cik"],
                )
            st.markdown(answer)
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"The assistant could not answer: {e}")

if history and st.button("Clear conversation"):
    st.session_state[thread_key] = []
    st.rerun()

st.caption("Credit analysis only — not investment advice.")
