"""
Offline checks against synthetic filings -- no network required.

Covers the cases that break naive implementations: quarterly durations mixed
into an annual filing, restated figures, negative equity, unclassified balance
sheets, and interest reported net of interest income.

Run:  python3 test_offline.py
"""

from sec_ratios import analyze, apply_overrides, compute, extract, inputs_table, to_table


def dur(start, end, val, filed="2024-02-01"):
    return {"start": start, "end": end, "val": val, "form": "10-K", "filed": filed}


def inst(end, val, filed="2024-02-01"):
    return {"end": end, "val": val, "form": "10-K", "filed": filed}


def usd(entries):
    return {"units": {"USD": entries}}


def build(name, tags):
    return {"entityName": name, "facts": {"us-gaap": tags}}


def show(payload):
    a = analyze(payload)
    header, rows = to_table(a)
    width = max(len(r[0]) for r in rows) + 2
    print(f"\n=== {a.entity} ===")
    print("".join([header[0].ljust(width)] + [h.rjust(28) for h in header[1:]]))
    for row in rows:
        print("".join([row[0].ljust(width)] + [c.rjust(28) for c in row[1:]]))
    for f in a.all_flags:
        print(f"  ! {f}")


# ---------------------------------------------------------------------------
# 1. Healthy industrial. Also seeds a stray quarterly duration and a stale
#    restatement to confirm both are filtered out.
# ---------------------------------------------------------------------------
healthy = build(
    "Standard Industrial Corp",
    {
        "NetIncomeLoss": usd(
            [
                dur("2022-01-01", "2022-12-31", 800_000_000),
                dur("2023-01-01", "2023-12-31", 900_000_000),
                dur("2024-01-01", "2024-12-31", 1_000_000_000),
                # quarterly figure inside the 10-K -- must be ignored
                dur("2024-10-01", "2024-12-31", 260_000_000),
                # stale restatement of FY2024 -- must lose to the later filing
                dur("2024-01-01", "2024-12-31", 111_111_111, filed="2023-01-01"),
            ]
        ),
        "StockholdersEquity": usd(
            [
                inst("2022-12-31", 4_000_000_000),
                inst("2023-12-31", 4_500_000_000),
                inst("2024-12-31", 5_000_000_000),
            ]
        ),
        "AssetsCurrent": usd(
            [inst("2022-12-31", 3_000_000_000), inst("2023-12-31", 3_200_000_000), inst("2024-12-31", 3_600_000_000)]
        ),
        "LiabilitiesCurrent": usd(
            [inst("2022-12-31", 2_000_000_000), inst("2023-12-31", 2_100_000_000), inst("2024-12-31", 2_200_000_000)]
        ),
        "Liabilities": usd(
            [inst("2022-12-31", 6_000_000_000), inst("2023-12-31", 6_300_000_000), inst("2024-12-31", 6_500_000_000)]
        ),
        "OperatingIncomeLoss": usd(
            [
                dur("2022-01-01", "2022-12-31", 1_100_000_000),
                dur("2023-01-01", "2023-12-31", 1_250_000_000),
                dur("2024-01-01", "2024-12-31", 1_400_000_000),
            ]
        ),
        # deliberately the second tag in the chain, to exercise the fallback
        "DepreciationAmortizationAndAccretionNet": usd(
            [
                dur("2022-01-01", "2022-12-31", 300_000_000),
                dur("2023-01-01", "2023-12-31", 320_000_000),
                dur("2024-01-01", "2024-12-31", 350_000_000),
            ]
        ),
        "InterestExpense": usd(
            [
                dur("2022-01-01", "2022-12-31", 150_000_000),
                dur("2023-01-01", "2023-12-31", 155_000_000),
                dur("2024-01-01", "2024-12-31", 160_000_000),
            ]
        ),
        "LongTermDebtNoncurrent": usd(
            [inst("2022-12-31", 2_500_000_000), inst("2023-12-31", 2_600_000_000), inst("2024-12-31", 2_700_000_000)]
        ),
        "LongTermDebtCurrent": usd(
            [inst("2022-12-31", 300_000_000), inst("2023-12-31", 300_000_000), inst("2024-12-31", 300_000_000)]
        ),
    },
)

# ---------------------------------------------------------------------------
# 2. Negative equity from buybacks, plus operating leases (the retailer case).
# ---------------------------------------------------------------------------
negative_equity = build(
    "Buyback Retail Inc",
    {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 17_000_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", -1_800_000_000)]),
        "AssetsCurrent": usd([inst("2024-12-31", 28_000_000_000)]),
        "LiabilitiesCurrent": usd([inst("2024-12-31", 26_000_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 78_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 21_000_000_000)]),
        "DepreciationDepletionAndAmortization": usd([dur("2024-01-01", "2024-12-31", 3_000_000_000)]),
        "InterestExpense": usd([dur("2024-01-01", "2024-12-31", 1_800_000_000)]),
        "LongTermDebtNoncurrent": usd([inst("2024-12-31", 42_000_000_000)]),
        "LongTermDebtCurrent": usd([inst("2024-12-31", 1_400_000_000)]),
        "OperatingLeaseLiabilityNoncurrent": usd([inst("2024-12-31", 6_500_000_000)]),
        "OperatingLeaseLiabilityCurrent": usd([inst("2024-12-31", 1_100_000_000)]),
    },
)

# ---------------------------------------------------------------------------
# 3. Bank: no current asset/liability split, interest reported net, total
#    liabilities untagged so it must be derived from assets minus equity.
# ---------------------------------------------------------------------------
bank = build(
    "Metropolitan Bancorp",
    {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 12_000_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 90_000_000_000)]),
        "Assets": usd([inst("2024-12-31", 900_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 15_000_000_000)]),
        "DepreciationAndAmortization": usd([dur("2024-01-01", "2024-12-31", 1_000_000_000)]),
        "InterestIncomeExpenseNet": usd([dur("2024-01-01", "2024-12-31", 500_000_000)]),
        "ShortTermBorrowings": usd([inst("2024-12-31", 40_000_000_000)]),
    },
)


# ---------------------------------------------------------------------------
# 4. Sparse filer: D&A, interest and debt all untagged. Nothing is wrong with
#    the filing -- the numbers are simply in the statements without standard
#    tags. This is the case the manual override exists for.
# ---------------------------------------------------------------------------
sparse = build(
    "Thinly Tagged Manufacturing",
    {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 400_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 2_500_000_000)]),
        "AssetsCurrent": usd([inst("2024-12-31", 1_800_000_000)]),
        "LiabilitiesCurrent": usd([inst("2024-12-31", 1_200_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 3_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 600_000_000)]),
    },
)


if __name__ == "__main__":
    for payload in (healthy, negative_equity, bank):
        show(payload)

    # --- Manual override round trip ---------------------------------------
    print("\n=== Sparse filer, before overrides ===")
    before = analyze(sparse)
    for row in to_table(before)[1]:
        print(f"{row[0]:<28}{row[1]:>34}")
    missing = before.years[0].missing()
    print(f"  missing inputs: {', '.join(missing)}")

    print("\n=== Sparse filer, after filling in from the filing ===")
    after = compute(
        apply_overrides(
            extract(sparse),
            {
                "2024-12-31": {
                    "da": 150_000_000,
                    "interest": 75_000_000,
                    "total_debt": 1_400_000_000,
                }
            },
        )
    )
    for row in to_table(after)[1]:
        print(f"{row[0]:<28}{row[1]:>34}")
    for f in after.all_flags:
        print(f"  ! {f}")

    # Assertions on the cases most likely to regress.
    a = analyze(healthy)
    fy24 = [y for y in a.years if y.period_end.year == 2024][0]
    assert fy24.ratios["Return on equity"] == "20.00%", fy24.ratios
    assert fy24.ratios["Current ratio"] == "1.64x", fy24.ratios
    assert fy24.ratios["Interest coverage"] == "8.75x", fy24.ratios
    assert fy24.ratios["Debt / EBITDA"] == "1.71x", fy24.ratios
    assert len(a.years) == 3

    b = analyze(negative_equity).years[0]
    assert "negative equity" in b.ratios["Return on equity"]
    assert "negative equity" in b.ratios["Debt / equity"]
    assert b.ratios["Debt / EBITDA"] == "1.81x", b.ratios
    assert b.ratios["Debt / EBITDA (lease-adj.)"] == "2.12x", b.ratios

    c = analyze(bank).years[0]
    assert "unclassified" in c.ratios["Current ratio"]
    assert c.ratios["Debt / equity"] == "9.00x", c.ratios
    assert any("net of interest income" in f for f in c.flags)

    # Overrides: missing before, computed after, and provenance recorded.
    s0 = analyze(sparse).years[0]
    assert set(s0.missing()) == {"da", "interest", "total_debt", "lease_liabilities"}
    assert s0.ratios["Interest coverage"] == "n/m - no interest expense reported"

    s1 = after.years[0]
    assert s1.ratios["Interest coverage"] == "8.00x", s1.ratios
    assert s1.ratios["Debt / EBITDA"] == "1.87x", s1.ratios
    assert set(s1.manual()) == {"da", "interest", "total_debt"}
    assert any("hand-entered" in f for f in s1.flags)

    # Overriding a filed value replaces it; None clears it back to missing.
    s2 = compute(
        apply_overrides(
            extract(sparse), {"2024-12-31": {"equity": 2_000_000_000, "net_income": None}}
        )
    ).years[0]
    assert s2.ratios["Debt / equity"] == "1.50x", s2.ratios
    assert s2.ratios["Return on equity"] == "not tagged", s2.ratios

    # Unknown field names are rejected rather than silently ignored.
    try:
        apply_overrides(extract(sparse), {"2024-12-31": {"ebitda": 1}})
        raise AssertionError("expected KeyError for unknown field")
    except KeyError:
        pass

    print("\nAll checks passed.")


def _grade_checks():
    """Colour bucketing, including the direction flip on leverage ratios."""
    from sec_ratios import GOOD, WATCH, WEAK, grade

    assert grade("Return on equity", 20.0) == GOOD
    assert grade("Return on equity", 8.0) == WATCH
    assert grade("Return on equity", 2.0) == WEAK

    assert grade("Current ratio", 1.8) == GOOD
    assert grade("Current ratio", 0.9) == WEAK

    # Lower is better here, so the buckets invert.
    assert grade("Debt / EBITDA", 1.5) == GOOD
    assert grade("Debt / EBITDA", 3.2) == WATCH
    assert grade("Debt / EBITDA", 6.0) == WEAK
    assert grade("Debt / equity", 0.8) == GOOD
    assert grade("Debt / equity", 3.0) == WEAK

    # Suppressed ratios have no number, so they get no colour.
    assert grade("Return on equity", None) is None
    assert grade("Something else", 1.0) is None

    neg = analyze(negative_equity).years[0]
    assert neg.values["Return on equity"] is None
    assert grade("Return on equity", neg.values["Return on equity"]) is None
    assert neg.values["Debt / EBITDA"] is not None

    print("Grade checks passed.")


_grade_checks()


def _assistant_checks():
    """The context block must carry everything the model is allowed to use."""
    from assistant import build_context, suggested_questions

    ctx = build_context(analyze(negative_equity), ticker="XYZ", cik="0000000123")
    assert "Buyback Retail Inc" in ctx and "XYZ" in ctx
    assert "n/m - negative equity" in ctx          # suppressed state is visible
    assert "[good]" in ctx                          # colour buckets travel too
    assert "Operating lease liabilities" in ctx
    assert "THRESHOLDS BEHIND THE COLOURS" in ctx

    qs = suggested_questions(analyze(negative_equity))
    assert any("ROE" in q for q in qs), qs

    # Hand-entered figures must be called out, and never as filed data.
    edited = compute(
        apply_overrides(extract(sparse), {"2024-12-31": {"da": 150_000_000}})
    )
    ctx2 = build_context(edited)
    assert "Hand-entered by the user" in ctx2
    assert "Never extracted, still unknown" in ctx2
    assert any("hand" in q.lower() for q in suggested_questions(edited))

    # A bank should prompt the liquidity question, not a current-ratio verdict.
    assert any("liquidity" in q for q in suggested_questions(analyze(bank)))

    print("Assistant context checks passed.")


_assistant_checks()


def _search_checks():
    """Search must return ticker/name/cik -- run.py and app.py index those keys.

    A duplicate definition of this method once shipped a 'title' key instead,
    which only surfaced as a KeyError against live data.
    """
    import inspect
    import json
    import pathlib
    import tempfile

    from sec_ratios import SecClient

    src = inspect.getsource(SecClient)
    assert src.count("def search") == 1, "SecClient.search is defined more than once"

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "company_tickers.json").write_text(
        json.dumps(
            {
                "0": {"cik_str": 320187, "ticker": "NKE", "title": "NIKE, Inc."},
                "1": {"cik_str": 354950, "ticker": "HD", "title": "HOME DEPOT, INC."},
                "2": {"cik_str": 99999, "ticker": "HDSN", "title": "HUDSON TECHNOLOGIES INC"},
            }
        )
    )
    c = SecClient(user_agent="test test@example.com", cache_dir=tmp)

    for query in ("NKE", "nke", "home depot", "hd"):
        hits = c.search(query)
        assert hits, f"no results for {query!r}"
        for h in hits:
            assert set(h) == {"ticker", "name", "cik"}, h

    assert c.search("NKE")[0]["ticker"] == "NKE"          # exact ticker wins
    assert c.search("hd")[0]["ticker"] == "HD"            # exact beats prefix
    assert len(c.search("hd")) == 2                       # HDSN still offered
    assert c.search("home depot")[0]["cik"] == "0000354950"
    assert c.search("zzzznotreal") == []

    print("Search checks passed.")


_search_checks()
