"""
Credit ratio extraction from SEC XBRL company facts.

Pulls annual (10-K) figures from SEC's structured data API and computes five
credit ratios across the last three fiscal years. No filing text is parsed.

Extraction and computation are deliberately separate. Filings resolve to a set
of raw inputs, any of which can be overridden by hand before ratios are
computed -- so an untagged or wrongly-tagged line item does not dead-end the
analysis. Manual values are tracked and surfaced, never silently blended in
with filed figures.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

# --------------------------------------------------------------------------
# SEC endpoints
# --------------------------------------------------------------------------

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

DEFAULT_UA = os.environ.get("SEC_USER_AGENT", "ratio-tool your.email@example.com")
CACHE_DIR = Path(os.environ.get("SEC_CACHE_DIR", Path.home() / ".sec_cache"))


# --------------------------------------------------------------------------
# Tag chains
# --------------------------------------------------------------------------

NET_INCOME = [
    "NetIncomeLoss",
    "ProfitLoss",
    "NetIncomeLossAvailableToCommonStockholdersBasic",
]
EQUITY = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
CURRENT_ASSETS = ["AssetsCurrent"]
CURRENT_LIABILITIES = ["LiabilitiesCurrent"]
TOTAL_ASSETS = ["Assets"]
TOTAL_LIABILITIES = ["Liabilities"]
OPERATING_INCOME = [
    "OperatingIncomeLoss",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
]
DA = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization",
]

# InterestIncomeExpenseNet is a last resort: netting interest income against
# expense shrinks the denominator and overstates coverage.
INTEREST = [
    "InterestExpense",
    "InterestExpenseDebt",
    "InterestExpenseNonoperating",
    "InterestIncomeExpenseNet",
]
INTEREST_NETTED = "InterestIncomeExpenseNet"

DEBT_COMPONENTS = [
    ["LongTermDebtNoncurrent", "LongTermDebt"],
    ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    ["ShortTermBorrowings", "OtherShortTermBorrowings", "CommercialPaper"],
]
DEBT_COMBINED = ["DebtLongtermAndShorttermCombinedAmount"]
LEASE_COMPONENTS = [
    ["OperatingLeaseLiabilityNoncurrent"],
    ["OperatingLeaseLiabilityCurrent"],
]


# --------------------------------------------------------------------------
# Input schema
# --------------------------------------------------------------------------
# Every ratio is computed from these ten fields and nothing else. Anything the
# filing does not supply can be typed in against the same names.


@dataclass(frozen=True)
class InputField:
    key: str
    label: str
    hint: str


INPUT_FIELDS: list[InputField] = [
    InputField("net_income", "Net income", "Bottom line, income statement"),
    InputField("equity", "Stockholders' equity", "Balance sheet, period end"),
    InputField("current_assets", "Current assets", "Absent on unclassified balance sheets"),
    InputField("current_liabilities", "Current liabilities", "Absent on unclassified balance sheets"),
    InputField("total_liabilities", "Total liabilities", "Derived from assets less equity if untagged"),
    InputField("ebit", "Operating income", "EBIT, before interest and tax"),
    InputField("da", "Depreciation & amortisation", "Usually off the cash flow statement"),
    InputField("interest", "Interest expense", "Gross, not net of interest income"),
    InputField("total_debt", "Total debt", "Long-term plus current maturities plus short-term"),
    InputField("lease_liabilities", "Operating lease liabilities", "Optional, for lease-adjusted leverage"),
]

FIELD_KEYS = [f.key for f in INPUT_FIELDS]
FIELD_LABELS = {f.key: f.label for f in INPUT_FIELDS}

MISSING = "not tagged"
MANUAL = "manual entry"
DERIVED = "derived"


# --------------------------------------------------------------------------
# SEC client
# --------------------------------------------------------------------------


class SecClient:
    """Fetches SEC data with on-disk caching."""

    def __init__(self, user_agent: str = DEFAULT_UA, cache_dir: Path = CACHE_DIR):
        self.headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_json(self, url: str, cache_name: str) -> dict:
        cached = self.cache_dir / cache_name
        if cached.exists():
            return json.loads(cached.read_text())

        import requests  # lazy so offline tests need no network deps

        resp = requests.get(url, headers=self.headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cached.write_text(json.dumps(data))
        return data

    def cik_for_ticker(self, ticker: str) -> str:
        data = self._get_json(TICKERS_URL, "company_tickers.json")
        target = ticker.strip().upper()
        for row in data.values():
            if row["ticker"].upper() == target:
                return str(row["cik_str"]).zfill(10)
        raise LookupError(f"No SEC filer found for ticker {target}")

    def search(self, query: str, limit: int = 12) -> list[dict]:
        """Find filers by ticker or company name.

        Exact ticker matches rank first, then names or tickers starting with the
        query, then names containing it. Someone typing 'home depot' should not
        have to know the ticker. Within each tier, shorter names sort first, so
        'NIKE, Inc.' beats a subsidiary with a longer legal name.

        Every result carries ticker, name and cik. Callers depend on those exact
        keys -- see run.py and app.py.
        """
        data = self._get_json(TICKERS_URL, "company_tickers.json")
        q = query.strip().lower()
        if not q:
            return []

        exact, starts, contains = [], [], []
        for row in data.values():
            entry = {
                "ticker": row["ticker"].upper(),
                "name": row["title"],
                "cik": str(row["cik_str"]).zfill(10),
            }
            ticker_l, name_l = entry["ticker"].lower(), entry["name"].lower()
            if ticker_l == q:
                exact.append(entry)
            elif name_l.startswith(q) or ticker_l.startswith(q):
                starts.append(entry)
            elif q in name_l:
                contains.append(entry)

        starts.sort(key=lambda e: len(e["name"]))
        contains.sort(key=lambda e: len(e["name"]))
        return (exact + starts + contains)[:limit]

    def cik_for_query(self, query: str) -> str:
        """Accept a ticker, a company name, or any SEC URL containing a CIK."""
        from_url = parse_cik_from_url(query)
        if from_url:
            return from_url
        matches = self.search(query, limit=1)
        if not matches:
            raise LookupError(f"No SEC filer found for '{query}'")
        return matches[0]["cik"]

    def company_facts(self, cik: str) -> dict:
        return self._get_json(FACTS_URL.format(cik=cik), f"facts_{cik}.json")

    def facts_for_ticker(self, ticker: str) -> dict:
        return self.company_facts(self.cik_for_ticker(ticker))

    def facts_for_cik(self, cik: str) -> dict:
        return self.company_facts(str(cik).zfill(10))


def parse_cik_from_url(text: str) -> str | None:
    """Pull a CIK out of a pasted SEC link.

    Handles the two shapes people copy: filing archive paths that carry the CIK
    as a path segment, and EDGAR browse pages that carry it as a query
    parameter. Returns None for anything that is not a SEC URL.
    """
    t = text.strip()
    if "sec.gov" not in t.lower():
        return None
    m = re.search(r"/data/(\d{1,10})", t) or re.search(r"CIK=(\d{1,10})", t, re.I)
    return m.group(1).zfill(10) if m else None


# --------------------------------------------------------------------------
# Fact extraction
# --------------------------------------------------------------------------


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _is_annual_form(entry: dict) -> bool:
    return str(entry.get("form", "")).startswith("10-K")


def _dedupe_latest(entries: Iterable[dict]) -> dict[date, float]:
    """One value per period end, keeping the most recently filed.

    The same fiscal year is reported and restated across several filings, so a
    naive pass produces duplicates and stale numbers.
    """
    best: dict[date, dict] = {}
    for e in entries:
        end = _parse(e["end"])
        prior = best.get(end)
        if prior is None or e.get("filed", "") > prior.get("filed", ""):
            best[end] = e
    return {end: float(e["val"]) for end, e in best.items()}


class FactStore:
    """Thin wrapper over the us-gaap block of a companyfacts payload."""

    def __init__(self, facts_payload: dict):
        self.entity = facts_payload.get("entityName", "Unknown filer")
        self._gaap = facts_payload.get("facts", {}).get("us-gaap", {})

    def _entries(self, tag: str) -> list[dict]:
        return list(self._gaap.get(tag, {}).get("units", {}).get("USD", []))

    def instant(self, tag: str) -> dict[date, float]:
        """Balance sheet items: point-in-time, no start date."""
        rows = [e for e in self._entries(tag) if _is_annual_form(e) and not e.get("start")]
        return _dedupe_latest(rows)

    def duration(self, tag: str) -> dict[date, float]:
        """Income and cash-flow items, restricted to ~12-month spans.

        Annual filings also carry quarterly durations for the same tag; without
        this filter you silently pick up a single quarter.
        """
        rows = []
        for e in self._entries(tag):
            if not _is_annual_form(e) or not e.get("start"):
                continue
            span = (_parse(e["end"]) - _parse(e["start"])).days
            if 340 <= span <= 400:
                rows.append(e)
        return _dedupe_latest(rows)

    def resolve(self, chain: list[str], kind: str) -> tuple[str | None, dict[date, float]]:
        """First tag in the chain that has data, with the series it produced."""
        getter = self.instant if kind == "instant" else self.duration
        for tag in chain:
            series = getter(tag)
            if series:
                return tag, series
        return None, {}


def _pick(series: dict[date, float], target: date, tol_days: int = 7) -> float | None:
    """Value at a period end, allowing small fiscal-calendar drift."""
    if target in series:
        return series[target]
    for end, val in series.items():
        if abs((end - target).days) <= tol_days:
            return val
    return None


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass
class YearResult:
    period_end: date
    inputs: dict[str, float | None] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    ratios: dict[str, str] = field(default_factory=dict)
    values: dict[str, float | None] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"FY{self.period_end.year}"

    @property
    def key(self) -> str:
        return self.period_end.isoformat()

    def missing(self) -> list[str]:
        return [k for k in FIELD_KEYS if self.inputs.get(k) is None]

    def manual(self) -> list[str]:
        return [k for k in FIELD_KEYS if self.sources.get(k) == MANUAL]


@dataclass
class Analysis:
    entity: str
    years: list[YearResult]

    @property
    def all_flags(self) -> list[str]:
        seen, out = set(), []
        for y in self.years:
            for f in y.flags:
                if f not in seen:
                    seen.add(f)
                    out.append(f)
        return out

    @property
    def has_manual(self) -> bool:
        return any(y.manual() for y in self.years)


RATIO_ORDER = [
    "Return on equity",
    "Current ratio",
    "Debt / equity",
    "Interest coverage",
    "Debt / EBITDA",
    "Debt / EBITDA (lease-adj.)",
]


def _fmt(value: float, suffix: str = "x") -> str:
    return f"{value:,.2f}{suffix}"


# --------------------------------------------------------------------------
# Grading
# --------------------------------------------------------------------------
# (strong_cut, weak_cut, direction). These are broad corporate-credit rules of
# thumb, not standards. A regulated utility at 4.5x leverage is unremarkable;
# a software company at the same level is stretched. Treat the colour as a
# prompt to look closer, never as a verdict.

GOOD, WATCH, WEAK = "good", "watch", "weak"

THRESHOLDS: dict[str, tuple[float, float, str]] = {
    "Return on equity": (15.0, 5.0, "higher"),
    "Current ratio": (1.5, 1.0, "higher"),
    "Debt / equity": (1.0, 2.0, "lower"),
    "Interest coverage": (4.0, 2.0, "higher"),
    "Debt / EBITDA": (2.5, 4.0, "lower"),
    "Debt / EBITDA (lease-adj.)": (3.0, 4.5, "lower"),
}

THRESHOLD_NOTES: dict[str, str] = {
    "Return on equity": "Strong above 15%, weak below 5%.",
    "Current ratio": "Strong above 1.5x, weak below 1.0x — under 1.0 means current bills exceed current assets.",
    "Debt / equity": "Strong below 1.0x, weak above 2.0x.",
    "Interest coverage": "Strong above 4x, weak below 2x — under 2x is distressed territory.",
    "Debt / EBITDA": "Strong below 2.5x, weak above 4.0x — most loan covenants sit near 3.5x.",
    "Debt / EBITDA (lease-adj.)": "Same idea, with leases capitalised, so the cutoffs sit higher.",
}


def grade(ratio_name: str, value: float | None) -> str | None:
    """Bucket a ratio as good / watch / weak, or None if not gradeable."""
    if value is None or ratio_name not in THRESHOLDS:
        return None
    strong, weak, direction = THRESHOLDS[ratio_name]
    if direction == "higher":
        if value >= strong:
            return GOOD
        return WATCH if value >= weak else WEAK
    if value <= strong:
        return GOOD
    return WATCH if value <= weak else WEAK


# --------------------------------------------------------------------------
# Health bands
# --------------------------------------------------------------------------
# (higher_is_better, good_at, poor_at). A ratio is GOOD past good_at, POOR past
# poor_at, MODERATE in between.
#
# These are screening heuristics, not credit policy. What counts as safe
# leverage is industry-specific: a regulated utility runs comfortably at levels
# that would be distress signals for a software company, because its cash flows
# are stable and its assets are financeable. Pick the profile that fits the
# borrower, and treat the colour as a prompt to look closer, never a verdict.

GOOD, MODERATE, POOR, UNRATED = "good", "moderate", "poor", "unrated"

THRESHOLD_PROFILES: dict[str, dict[str, tuple[bool, float, float]]] = {
    "General corporate": {
        "Return on equity": (True, 15.0, 8.0),
        "Current ratio": (True, 1.50, 1.00),
        "Debt / equity": (False, 1.00, 2.50),
        "Interest coverage": (True, 6.00, 2.00),
        "Debt / EBITDA": (False, 2.50, 4.00),
        "Debt / EBITDA (lease-adj.)": (False, 3.00, 4.50),
    },
    "Capital intensive (utilities, telecom, transport)": {
        "Return on equity": (True, 10.0, 5.0),
        "Current ratio": (True, 1.20, 0.80),
        "Debt / equity": (False, 1.50, 3.50),
        "Interest coverage": (True, 3.50, 1.50),
        "Debt / EBITDA": (False, 4.00, 6.00),
        "Debt / EBITDA (lease-adj.)": (False, 4.50, 6.50),
    },
    "Asset light (software, services)": {
        "Return on equity": (True, 20.0, 10.0),
        "Current ratio": (True, 1.80, 1.20),
        "Debt / equity": (False, 0.75, 2.00),
        "Interest coverage": (True, 10.00, 3.00),
        "Debt / EBITDA": (False, 1.50, 3.00),
        "Debt / EBITDA (lease-adj.)": (False, 2.00, 3.50),
    },
}

DEFAULT_PROFILE = "General corporate"


def rating(ratio_name: str, value: float | None, profile: str = DEFAULT_PROFILE) -> str:
    """Classify one ratio as good, moderate, poor, or unrated."""
    if value is None:
        return UNRATED
    band = THRESHOLD_PROFILES.get(profile, {}).get(ratio_name)
    if band is None:
        return UNRATED
    higher_is_better, good_at, poor_at = band
    if higher_is_better:
        if value >= good_at:
            return GOOD
        return MODERATE if value > poor_at else POOR
    if value <= good_at:
        return GOOD
    return MODERATE if value < poor_at else POOR


def band_text(ratio_name: str, profile: str = DEFAULT_PROFILE) -> str:
    """Plain-language description of where the cut-offs sit."""
    band = THRESHOLD_PROFILES.get(profile, {}).get(ratio_name)
    if band is None:
        return ""
    higher_is_better, good_at, poor_at = band
    unit = "%" if ratio_name == "Return on equity" else "x"
    if higher_is_better:
        return f"green at or above {good_at:g}{unit}, red at or below {poor_at:g}{unit}"
    return f"green at or below {good_at:g}{unit}, red at or above {poor_at:g}{unit}"


# --------------------------------------------------------------------------
# Step 1: extract raw inputs
# --------------------------------------------------------------------------


def _sum_components(
    store: FactStore, chains: list[list[str]], target: date
) -> tuple[float | None, str]:
    """Sum optional balance sheet components, reporting the tags used."""
    total, used = 0.0, []
    for chain in chains:
        tag, series = store.resolve(chain, "instant")
        val = _pick(series, target) if series else None
        if val is not None:
            total += val
            used.append(tag)
    if not used:
        return None, MISSING
    return total, " + ".join(used)


def extract(facts_payload: dict, years: int = 3) -> Analysis:
    """Resolve filings into raw inputs. No ratios computed yet."""
    store = FactStore(facts_payload)

    _, net_income = store.resolve(NET_INCOME, "duration")
    if not net_income:
        raise ValueError(
            "No annual net income found. The filer may report in a currency other "
            "than USD, or may not file 10-Ks."
        )

    period_ends = sorted(net_income.keys(), reverse=True)[:years]

    simple = [
        ("net_income", NET_INCOME, "duration"),
        ("equity", EQUITY, "instant"),
        ("current_assets", CURRENT_ASSETS, "instant"),
        ("current_liabilities", CURRENT_LIABILITIES, "instant"),
        ("total_liabilities", TOTAL_LIABILITIES, "instant"),
        ("ebit", OPERATING_INCOME, "duration"),
        ("da", DA, "duration"),
        ("interest", INTEREST, "duration"),
    ]
    resolved = {key: store.resolve(chain, kind) for key, chain, kind in simple}
    _, assets_s = store.resolve(TOTAL_ASSETS, "instant")

    results = []
    for pe in period_ends:
        r = YearResult(period_end=pe)

        for key, (tag, series) in resolved.items():
            val = _pick(series, pe) if series else None
            r.inputs[key] = val
            r.sources[key] = tag if val is not None else MISSING

        debt, debt_src = _sum_components(store, DEBT_COMPONENTS, pe)
        if debt is None:
            tag, combined = store.resolve(DEBT_COMBINED, "instant")
            val = _pick(combined, pe) if combined else None
            if val is not None:
                debt, debt_src = val, tag
        r.inputs["total_debt"], r.sources["total_debt"] = debt, debt_src

        leases, lease_src = _sum_components(store, LEASE_COMPONENTS, pe)
        r.inputs["lease_liabilities"], r.sources["lease_liabilities"] = leases, lease_src

        # Total liabilities is occasionally untagged; derive where possible.
        if r.inputs["total_liabilities"] is None:
            assets = _pick(assets_s, pe)
            if assets is not None and r.inputs["equity"] is not None:
                r.inputs["total_liabilities"] = assets - r.inputs["equity"]
                r.sources["total_liabilities"] = DERIVED

        results.append(r)

    return Analysis(entity=store.entity, years=results)


# --------------------------------------------------------------------------
# Step 2: apply manual overrides
# --------------------------------------------------------------------------


def apply_overrides(analysis: Analysis, overrides: dict[str, dict[str, float | None]]) -> Analysis:
    """Replace inputs with hand-entered values.

    Keyed by ISO period end, then field key; values in dollars. Passing None
    clears a field back to missing, so a wrongly-tagged figure can be removed
    as well as replaced.
    """
    for year in analysis.years:
        for key, val in (overrides.get(year.key) or {}).items():
            if key not in FIELD_KEYS:
                raise KeyError(f"Unknown input field: {key}")
            year.inputs[key] = val
            year.sources[key] = MANUAL if val is not None else MISSING
    return analysis


# --------------------------------------------------------------------------
# Step 3: compute ratios
# --------------------------------------------------------------------------


def compute(analysis: Analysis) -> Analysis:
    """Compute ratios from whatever inputs are present, filed or manual."""
    for r in analysis.years:
        r.ratios, r.values, r.flags = {}, {}, []
        i = r.inputs

        def put(name: str, value: float | None, text: str) -> None:
            """Record a ratio twice: as a number for colouring, as text to show."""
            r.values[name] = value
            r.ratios[name] = text

        ni, eq = i.get("net_income"), i.get("equity")
        ca, cl = i.get("current_assets"), i.get("current_liabilities")
        liab, ebit = i.get("total_liabilities"), i.get("ebit")
        da, interest = i.get("da"), i.get("interest")
        debt, leases = i.get("total_debt"), i.get("lease_liabilities")

        # --- Return on equity -------------------------------------------
        if ni is None or eq is None:
            put("Return on equity", None, MISSING)
        elif eq <= 0:
            put("Return on equity", None, "n/m - negative equity")
            r.flags.append(
                "Equity is negative, typically from sustained buybacks. ROE and D/E "
                "are not meaningful; read leverage off Debt/EBITDA instead."
            )
        else:
            roe = 100 * ni / eq
            put("Return on equity", roe, _fmt(roe, "%"))

        # --- Current ratio ----------------------------------------------
        if ca is None or cl is None:
            put("Current ratio", None, "n/a - unclassified balance sheet")
            r.flags.append(
                "No current asset/liability split. Banks and insurers file "
                "unclassified balance sheets; liquidity needs a different lens."
            )
        elif cl == 0:
            put("Current ratio", None, MISSING)
        else:
            put("Current ratio", ca / cl, _fmt(ca / cl))

        # --- Debt / equity ----------------------------------------------
        if liab is None or eq is None:
            put("Debt / equity", None, MISSING)
        elif eq <= 0:
            put("Debt / equity", None, "n/m - negative equity")
        else:
            put("Debt / equity", liab / eq, _fmt(liab / eq))

        # --- Interest coverage ------------------------------------------
        if ebit is None:
            put("Interest coverage", None, MISSING)
        elif interest is None or interest == 0:
            put("Interest coverage", None, "n/m - no interest expense reported")
        else:
            cov = ebit / abs(interest)
            put("Interest coverage", cov, _fmt(cov))
            if r.sources.get("interest") == INTEREST_NETTED:
                r.flags.append(
                    "Interest is reported net of interest income, so coverage is "
                    "overstated. Enter gross interest expense to correct it."
                )

        # --- Debt / EBITDA ----------------------------------------------
        ebitda = None if (ebit is None or da is None) else ebit + da
        if ebitda is None or debt is None:
            put("Debt / EBITDA", None, MISSING)
        elif ebitda <= 0:
            put("Debt / EBITDA", None, "n/m - negative EBITDA")
        else:
            put("Debt / EBITDA", debt / ebitda, _fmt(debt / ebitda))
            if leases:
                lev = (debt + leases) / ebitda
                put("Debt / EBITDA (lease-adj.)", lev, _fmt(lev))
                r.flags.append(
                    "Lease-adjusted leverage adds capitalised operating leases to debt, "
                    "as rating agencies do. It matters most for retail and airlines."
                )

        # --- Provenance --------------------------------------------------
        if r.sources.get("total_liabilities") == DERIVED:
            r.flags.append("Total liabilities derived as assets less equity.")
        if r.manual():
            names = ", ".join(FIELD_LABELS[k] for k in r.manual())
            r.flags.append(f"{r.label} uses hand-entered figures for: {names}.")

    return analysis


def analyze(
    facts_payload: dict,
    years: int = 3,
    overrides: dict[str, dict[str, float | None]] | None = None,
) -> Analysis:
    """Extract, override, compute."""
    a = extract(facts_payload, years=years)
    if overrides:
        a = apply_overrides(a, overrides)
    return compute(a)


def to_table(analysis: Analysis) -> tuple[list[str], list[list[str]]]:
    """(header, rows) with fiscal years as columns, oldest first."""
    years = sorted(analysis.years, key=lambda y: y.period_end)
    header = ["Ratio"] + [y.label for y in years]
    present = [r for r in RATIO_ORDER if any(r in y.ratios for y in years)]
    rows = [[r] + [y.ratios.get(r, MISSING) for y in years] for r in present]
    return header, rows


def ratings_table(analysis: Analysis, profile: str = DEFAULT_PROFILE) -> list[list[str]]:
    """Health class per cell, matching the shape of to_table's rows."""
    years = sorted(analysis.years, key=lambda y: y.period_end)
    present = [r for r in RATIO_ORDER if any(r in y.ratios for y in years)]
    return [[rating(r, y.values.get(r), profile) for y in years] for r in present]


def inputs_table(analysis: Analysis) -> tuple[list[str], list[list[str]]]:
    """Raw inputs in $ millions, with the tag or source behind each figure."""
    years = sorted(analysis.years, key=lambda y: y.period_end)
    header = ["Input"] + [y.label for y in years] + ["Source (latest year)"]
    rows = []
    for f in INPUT_FIELDS:
        cells = []
        for y in years:
            v = y.inputs.get(f.key)
            cells.append("--" if v is None else f"{v / 1e6:,.0f}")
        rows.append([f.label] + cells + [years[-1].sources.get(f.key, MISSING)])
    return header, rows
