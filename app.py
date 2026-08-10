"""
Streamlit front end.

Flow: search for a company, pull its filings, show colour-coded ratios, and
offer manual entry for anything the filing did not tag.

Run with: streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st

import assistant
from sec_ratios import (
    GOOD,
    INPUT_FIELDS,
    MISSING,
    THRESHOLD_NOTES,
    WATCH,
    WEAK,
    SecClient,
    apply_overrides,
    compute,
    extract,
    grade,
    inputs_table,
    to_table,
)

st.set_page_config(page_title="Credit ratios from SEC filings", layout="centered")

# Light fills with dark text, so cells stay readable in either Streamlit theme.
CELL_STYLE = {
    GOOD: "background-color: #d1f0da; color: #14532d",
    WATCH: "background-color: #fdf0c8; color: #713f12",
    WEAK: "background-color: #fadadd; color: #7f1d1d",
}

st.title("Credit ratios from SEC filings")
st.write(
    "Search for a company to pull its last three annual reports straight from "
    "SEC's XBRL data and compute the ratios a credit analyst reads first."
)

user_agent = os.environ.get("SEC_USER_AGENT")
if not user_agent:
    st.error(
        "Set the SEC_USER_AGENT environment variable to your name and email "
        "before running. SEC rejects requests that do not identify the caller."
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


# --------------------------------------------------------------------------
# 1. Find the company
# --------------------------------------------------------------------------

query = st.text_input("Company name or ticker", placeholder="Home Depot").strip()

if not query:
    st.caption(
        "Try Home Depot to see negative equity, or JPMorgan for a bank balance sheet."
    )
    st.stop()

try:
    matches = search(query)
except Exception as e:
    st.error(f"Could not reach SEC: {e}")
    st.stop()

if not matches:
    st.warning(f"Nothing matches “{query}”. Try a shorter name or the ticker.")
    st.stop()

if len(matches) == 1:
    chosen = matches[0]
    st.caption(f"Matched {chosen['name']} ({chosen['ticker']})")
else:
    chosen = st.selectbox(
        "Which company?",
        matches,
        format_func=lambda m: f"{m['name']} ({m['ticker']})",
    )

# --------------------------------------------------------------------------
# 2. Pull the filings
# --------------------------------------------------------------------------

try:
    with st.spinner(f"Fetching {chosen['ticker']} filings"):
        payload = fetch(chosen["cik"])
    base = extract(payload)
except ValueError as e:
    st.warning(str(e))
    st.stop()
except Exception as e:
    st.error(f"Could not load filings: {e}")
    st.stop()

years = sorted(base.years, key=lambda y: y.period_end)


def widget_key(year_key: str, field_key: str) -> str:
    return f"{chosen['cik']}|{year_key}|{field_key}"


# --------------------------------------------------------------------------
# 3. Manual entry for anything untagged
# --------------------------------------------------------------------------
# Widgets pre-fill with the filed figure rounded to $ millions. A value still
# matching its prefill is not an override, so untouched fields stay attributed
# to the filing.

prefill: dict[str, dict[str, float | None]] = {
    y.key: {
        f.key: (None if y.inputs.get(f.key) is None else float(round(y.inputs[f.key] / 1e6)))
        for f in INPUT_FIELDS
    }
    for y in years
}

missing_now = sum(len(y.missing()) for y in years)

if missing_now:
    st.info(
        f"{missing_now} figure(s) were not tagged in these filings. Open the panel "
        "below to type them in from the statements, or leave them blank and the "
        "affected ratios will stay marked unavailable."
    )

with st.expander(
    f"Fill in or correct figures ({missing_now} not tagged)"
    if missing_now
    else "Fill in or correct figures",
    expanded=bool(missing_now),
):
    st.caption(
        "All figures in $ millions. Blank means the filing did not tag it. "
        "Clearing a field removes it again."
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
                    + ("not tagged, enter manually" if src == MISSING else f"tag: {src}"),
                )

overrides: dict[str, dict[str, float | None]] = {}
for y in years:
    changed = {}
    for f in INPUT_FIELDS:
        entered = st.session_state.get(widget_key(y.key, f.key))
        if entered != prefill[y.key][f.key]:
            changed[f.key] = None if entered is None else float(entered) * 1e6
    if changed:
        overrides[y.key] = changed

result = compute(apply_overrides(base, overrides))

# --------------------------------------------------------------------------
# 4. Show the ratios, colour-coded
# --------------------------------------------------------------------------

st.subheader(result.entity)

header, rows = to_table(result)
table = pd.DataFrame(rows, columns=header)

ordered = sorted(result.years, key=lambda y: y.period_end)


def colour(_frame: pd.DataFrame) -> pd.DataFrame:
    """CSS for every cell: ratio rows get a colour, the label column never does."""
    css = pd.DataFrame("", index=table.index, columns=table.columns)
    for row_i, name in enumerate(table[header[0]]):
        for col_i, y in enumerate(ordered, start=1):
            bucket = grade(name, y.values.get(name))
            if bucket:
                css.iloc[row_i, col_i] = CELL_STYLE[bucket]
    return css


st.dataframe(
    table.style.apply(colour, axis=None),
    hide_index=True,
    use_container_width=True,
)

st.markdown(
    f"<span style='{CELL_STYLE[GOOD]};padding:2px 8px;border-radius:3px'>strong</span> "
    f"<span style='{CELL_STYLE[WATCH]};padding:2px 8px;border-radius:3px'>watch</span> "
    f"<span style='{CELL_STYLE[WEAK]};padding:2px 8px;border-radius:3px'>weak</span> "
    "&nbsp; Uncoloured cells could not be computed or are not meaningful.",
    unsafe_allow_html=True,
)

if result.all_flags:
    st.markdown("**How to read this**")
    for flag in result.all_flags:
        st.markdown(f"- {flag}")

with st.expander("What the colours mean"):
    st.caption(
        "Broad corporate rules of thumb, not standards. Normal leverage varies "
        "widely by industry — a utility at 4.5x is unremarkable, a software company "
        "at the same level is stretched. Read a colour as a prompt to look closer, "
        "never as a verdict."
    )
    for name, note in THRESHOLD_NOTES.items():
        st.markdown(f"- **{name}** — {note}")

with st.expander("Show the underlying figures"):
    ih, ir = inputs_table(result)
    st.dataframe(pd.DataFrame(ir, columns=ih), hide_index=True, use_container_width=True)
    st.caption("$ millions. Source shows the XBRL tag behind the most recent year.")

# --------------------------------------------------------------------------
# 5. Ask the assistant
# --------------------------------------------------------------------------
# The model sees only the table above. It has no search, no memory of the
# filing text, and is instructed to refuse rather than supply a figure that is
# not in front of it.

if not assistant.available(): st.stop()
st.divider()
st.subheader("Ask about these numbers")

if not assistant.available():
    st.info(
        "Set ANTHROPIC_API_KEY to turn on the assistant. Everything else in the "
        "tool works without it."
    )
else:
    thread_key = f"chat_{chosen['cik']}"
    history = st.session_state.setdefault(thread_key, [])

    st.caption(
        "Answers come only from the figures above — the assistant cannot look "
        "anything up and will say so when the tool did not extract something."
    )

    pending = None
    if not history:
        cols = st.columns(2)
        for n, q in enumerate(assistant.suggested_questions(result)):
            if cols[n % 2].button(q, key=f"sq{n}", use_container_width=True):
                pending = q

    for turn in history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    typed = st.chat_input("e.g. is this leverage a problem for a retailer?")
    question = typed or pending

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            try:
                with st.spinner("Reading the figures"):
                    answer = assistant.ask(
                        result,
                        question,
                        history=history,
                        ticker=chosen["ticker"],
                        cik=chosen["cik"],
                    )
                st.markdown(answer)
                # Store the bare question; the figures are re-attached each turn
                # so edits to the table take effect immediately.
                history.append({"role": "user", "content": question})
                history.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"The assistant could not answer: {e}")

    if history and st.button("Clear conversation"):
        st.session_state[thread_key] = []
        st.rerun()

    st.caption(
        "Credit analysis only — not investment advice, and no substitute for "
        "reading the filing."
    )

st.caption(
    "Figures come from XBRL tags in filed 10-Ks. Ratios use ending balance sheet "
    "values, not period averages. Debt is long-term debt plus current maturities "
    "plus short-term borrowings."
)
