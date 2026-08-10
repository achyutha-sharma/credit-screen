"""
Grounded analyst assistant.

The model never fetches anything and never recalls figures from memory. Every
question is answered against a context block built from the ratios and inputs
already on screen, including which figures were filed, derived or hand-entered.
If a question cannot be answered from that block, the correct answer is to say
so and name what is missing.

That constraint is the point. An unconstrained model asked "how levered is this
company" will produce a confident number from training data that may be years
stale, and the user has no way to tell it apart from the filed figure.
"""

from __future__ import annotations

import os

from sec_ratios import (
    FIELD_LABELS,
    MANUAL,
    MISSING,
    RATIO_ORDER,
    THRESHOLD_NOTES,
    Analysis,
    grade,
)

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_TOKENS = 900

SYSTEM_PROMPT = """You are a credit analyst's assistant embedded in a ratio screening tool.

GROUNDING RULES — these override everything else:
- Answer only from the FIGURES block in the user message. It is the complete set
  of data you have.
- Never state a financial figure that does not appear in that block. Do not
  recall revenue, debt, ratings, share prices or any other number from memory,
  even if you are confident. If asked for something not in the block, say plainly
  that the tool did not extract it and name what would be needed.
- Never estimate, extrapolate or fill a gap with a typical value.
- Distinguish filed figures from hand-entered ones. If an answer leans on a
  hand-entered figure, say so.
- If a ratio is marked not meaningful, explain why it was suppressed rather than
  treating it as a bad score.

ANALYTICAL STANCE:
- You read these as a credit analyst: can this borrower service and repay its
  debt. Profitability matters only as it supports that.
- The colour thresholds are generic corporate rules of thumb. Say when industry
  context would change the read — banks, utilities, REITs and airlines all carry
  leverage that would look alarming on an industrial.
- Trends across the three years usually matter more than any single level.
- Point to what the analyst should check next in the filing: covenant terms,
  maturity walls, off-balance-sheet items, revenue concentration.

BOUNDARIES:
- No investment advice. Do not suggest buying, selling or holding securities,
  and do not forecast share prices. If asked, redirect to what the credit
  picture shows.
- You are not a substitute for reading the filing or for credit committee.

STYLE: concise and direct. Short paragraphs, no preamble, no restating the
question. Numbers in $ millions as given. Two or three tight paragraphs is
usually right; use bullets only for genuine lists."""


# --------------------------------------------------------------------------
# Context block
# --------------------------------------------------------------------------


def _fmt_row(label: str, cells: list[str], width: int = 30, cell: int = 14) -> str:
    return label.ljust(width) + "".join(str(c).rjust(cell) for c in cells)


def _fmt_src_row(label: str, cells: list[str], source: str) -> str:
    return _fmt_row(label, cells) + "   " + source


def build_context(analysis: Analysis, ticker: str = "", cik: str = "") -> str:
    """Everything the model is allowed to reason from, as plain text."""
    years = sorted(analysis.years, key=lambda y: y.period_end)
    labels = [y.label for y in years]

    head = f"COMPANY: {analysis.entity}"
    if ticker:
        head += f" ({ticker})"
    if cik:
        head += f"  CIK {cik}"

    lines = [
        "FIGURES",
        "=" * 62,
        head,
        f"PERIODS: {', '.join(labels)}  (annual, Form 10-K)",
        "",
        "RATIOS",
        _fmt_row("", labels),
    ]

    for name in RATIO_ORDER:
        if not any(name in y.ratios for y in years):
            continue
        cells = []
        for y in years:
            text = y.ratios.get(name, MISSING)
            bucket = grade(name, y.values.get(name))
            cells.append(f"{text}{'' if not bucket else f' [{bucket}]'}")
        lines.append(_fmt_row(name, cells, cell=24))

    lines += ["", "INPUTS ($ millions)", _fmt_row("", labels) + "   source (latest year)"]
    for key, label in FIELD_LABELS.items():
        cells = []
        for y in years:
            v = y.inputs.get(key)
            cells.append("--" if v is None else f"{v / 1e6:,.0f}")
        lines.append(_fmt_src_row(label, cells, years[-1].sources.get(key, MISSING)))

    manual = sorted({FIELD_LABELS[k] for y in years for k in y.manual()})
    missing = sorted({FIELD_LABELS[k] for y in years for k in y.missing()})

    lines += ["", "DATA NOTES"]
    if not analysis.all_flags and not manual and not missing:
        lines.append("- Every input was tagged in the filings. No adjustments made.")
    for f in analysis.all_flags:
        lines.append(f"- {f}")
    if manual:
        lines.append(f"- Hand-entered by the user, not from the filing: {', '.join(manual)}.")
    if missing:
        lines.append(f"- Never extracted, still unknown: {', '.join(missing)}.")

    lines += ["", "THRESHOLDS BEHIND THE COLOURS"]
    for name, note in THRESHOLD_NOTES.items():
        if any(name in y.ratios for y in years):
            lines.append(f"- {name}: {note}")

    lines.append("=" * 62)
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Starter questions
# --------------------------------------------------------------------------


def suggested_questions(analysis: Analysis) -> list[str]:
    """Openers drawn from what is actually unusual about this company."""
    years = sorted(analysis.years, key=lambda y: y.period_end)
    latest = years[-1]
    qs = ["What stands out in these numbers?"]

    text = " ".join(latest.ratios.values())
    if "negative equity" in text:
        qs.append("Why are ROE and D/E not shown?")
    if "unclassified" in text:
        qs.append("How do I judge liquidity without a current ratio?")
    if any("net of interest income" in f for f in analysis.all_flags):
        qs.append("How much could interest coverage be overstated?")
    if "Debt / EBITDA (lease-adj.)" in latest.ratios:
        qs.append("How much does capitalising leases change the leverage picture?")
    if any(y.manual() for y in years):
        qs.append("Which figures were entered by hand, and does that change anything?")

    if len(years) > 1:
        worsened = [
            n
            for n in RATIO_ORDER
            if (a := years[0].values.get(n)) is not None
            and (b := latest.values.get(n)) is not None
            and grade(n, b) != grade(n, a)
        ]
        if worsened:
            qs.append(f"What changed in {worsened[0].lower()} over the three years?")

    weak = [n for n in RATIO_ORDER if grade(n, latest.values.get(n)) == "weak"]
    if weak:
        qs.append(f"Is {weak[0].lower()} at this level a real problem here?")

    qs.append("What should I check in the filing next?")
    return qs[:5]


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def available() -> bool:
    """True when an API key is configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ask(
    analysis: Analysis,
    question: str,
    history: list[dict] | None = None,
    ticker: str = "",
    cik: str = "",
    model: str = MODEL,
) -> str:
    """Answer one question against the current figures.

    History is a list of {"role", "content"} dicts from earlier turns. The
    context block is attached to the newest question only, so a long
    conversation does not repeat it, and edits to the figures take effect
    immediately on the next turn.
    """
    if not available():
        raise RuntimeError(
            "Set ANTHROPIC_API_KEY to use the assistant. Everything else in the "
            "tool works without it."
        )

    import anthropic  # lazy so the tool runs without the SDK installed

    context = build_context(analysis, ticker=ticker, cik=cik)
    messages = list(history or [])
    messages.append({"role": "user", "content": f"{context}\n\nQUESTION: {question}"})

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    return "".join(block.text for block in resp.content if block.type == "text")
