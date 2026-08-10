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


def _interest_checks():
    """Cash-interest fallback, and net interest income that has no denominator."""
    from sec_ratios import CASH_INTEREST_TAGS, INTEREST, NETTED_INTEREST_TAGS

    # Preference order: gross expense, then cash paid, then netted.
    assert INTEREST.index("InterestExpense") < INTEREST.index("InterestPaidNet")
    assert INTEREST.index("InterestPaidNet") < INTEREST.index("InterestIncomeExpenseNet")
    assert NETTED_INTEREST_TAGS <= set(INTEREST) and CASH_INTEREST_TAGS <= set(INTEREST)

    base = {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 5_000_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 14_000_000_000)]),
        "AssetsCurrent": usd([inst("2024-12-31", 25_000_000_000)]),
        "LiabilitiesCurrent": usd([inst("2024-12-31", 10_000_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 23_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 6_000_000_000)]),
        "DepreciationDepletionAndAmortization": usd([dur("2024-01-01", "2024-12-31", 700_000_000)]),
        "LongTermDebtNoncurrent": usd([inst("2024-12-31", 9_000_000_000)]),
    }

    # Only cash interest tagged -- usable, but flagged as cash not accrual.
    cash = analyze(build("Cash Interest Co", {**base,
        "InterestPaidNet": usd([dur("2024-01-01", "2024-12-31", 300_000_000)])})).years[0]
    assert cash.ratios["Interest coverage"] == "20.00x", cash.ratios
    assert any("cash interest paid" in f for f in cash.flags), cash.flags

    # Net figure is income, not expense: no denominator exists.
    inc = analyze(build("Net Interest Income Co", {**base,
        "InterestIncomeExpenseNonoperatingNet": usd(
            [dur("2024-01-01", "2024-12-31", -120_000_000)])})).years[0]
    assert inc.ratios["Interest coverage"] == "n/m - net interest income", inc.ratios
    assert inc.values["Interest coverage"] is None
    assert any("no coverage ratio exists" in f for f in inc.flags), inc.flags

    # A positive netted figure still computes, still warns.
    net = analyze(build("Netted Co", {**base,
        "InterestIncomeExpenseNonoperatingNet": usd(
            [dur("2024-01-01", "2024-12-31", 200_000_000)])})).years[0]
    assert net.ratios["Interest coverage"] == "30.00x", net.ratios
    assert any("net of interest income" in f for f in net.flags), net.flags

    # Gross beats cash when both are present.
    both = analyze(build("Both Co", {**base,
        "InterestExpense": usd([dur("2024-01-01", "2024-12-31", 500_000_000)]),
        "InterestPaidNet": usd([dur("2024-01-01", "2024-12-31", 300_000_000)])})).years[0]
    assert both.ratios["Interest coverage"] == "12.00x", both.ratios
    assert not any("cash interest" in f for f in both.flags)

    print("Interest checks passed.")


def _search_ranking_checks():
    """Word-boundary matching, and one row per filer."""
    import json, pathlib, tempfile
    from sec_ratios import SecClient

    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / "company_tickers.json").write_text(json.dumps({
        "0": {"cik_str": 320187, "ticker": "NKE",    "title": "NIKE, Inc."},
        "1": {"cik_str": 703351, "ticker": "EAT",    "title": "BRINKER INTERNATIONAL, INC"},
        "2": {"cik_str": 39263,  "ticker": "CFR",    "title": "CULLEN/FROST BANKERS, INC."},
        "3": {"cik_str": 39263,  "ticker": "CFR-PB", "title": "CULLEN/FROST BANKERS, INC."},
        "4": {"cik_str": 354950, "ticker": "HD",     "title": "HOME DEPOT, INC."},
    }))
    c = SecClient(user_agent="test test@example.com", cache_dir=tmp)

    # "nke" must not drag in BRI-NKE-R or BA-NKE-RS.
    assert [h["ticker"] for h in c.search("NKE")] == ["NKE"], c.search("NKE")

    # Same CIK under two tickers collapses to one row.
    cullen = c.search("cullen")
    assert len(cullen) == 1 and cullen[0]["cik"] == "0000039263", cullen

    assert c.search("home depot")[0]["ticker"] == "HD"
    assert c.search("brinker")[0]["ticker"] == "EAT"
    print("Search ranking checks passed.")


_interest_checks()
_search_ranking_checks()


def _per_year_resolution_checks():
    """A filer that switches tags between years must resolve every year.

    Resolving a chain once for the whole company picked the first tag with any
    data, then looked it up per period -- so years using a later tag in the
    chain came back blank. Home Depot showed interest coverage in one year and
    'not reported' in the next two, from the same filing.
    """
    switcher = build("Tag Switching Corp", {
        "NetIncomeLoss": usd([
            dur("2023-01-01", "2023-12-31", 1_000_000_000),
            dur("2024-01-01", "2024-12-31", 1_100_000_000),
        ]),
        "StockholdersEquity": usd([inst("2023-12-31", 5_000_000_000),
                                   inst("2024-12-31", 5_400_000_000)]),
        "Liabilities": usd([inst("2023-12-31", 6_000_000_000),
                            inst("2024-12-31", 6_200_000_000)]),
        "OperatingIncomeLoss": usd([
            dur("2023-01-01", "2023-12-31", 1_500_000_000),
            dur("2024-01-01", "2024-12-31", 1_600_000_000),
        ]),
        # Interest tagged one way in FY2023, another in FY2024.
        "InterestExpense": usd([dur("2023-01-01", "2023-12-31", 150_000_000)]),
        "InterestExpenseNonoperating": usd([dur("2024-01-01", "2024-12-31", 160_000_000)]),
        # Debt likewise moves between tags.
        "LongTermDebtNoncurrent": usd([inst("2023-12-31", 3_000_000_000)]),
        "LongTermDebt": usd([inst("2024-12-31", 3_200_000_000)]),
        "DepreciationDepletionAndAmortization": usd([
            dur("2023-01-01", "2023-12-31", 300_000_000),
            dur("2024-01-01", "2024-12-31", 320_000_000),
        ]),
    })
    a = analyze(switcher)
    by_year = {y.label: y for y in a.years}

    for label in ("FY2023", "FY2024"):
        y = by_year[label]
        assert y.inputs["interest"] is not None, f"{label} lost interest"
        assert y.inputs["total_debt"] is not None, f"{label} lost debt"
        assert y.ratios["Interest coverage"] != "n/m - no interest expense reported", label
        assert y.ratios["Debt / EBITDA"] != "not tagged", label

    # Each year records the tag it actually used, not a company-wide winner.
    assert by_year["FY2023"].sources["interest"] == "InterestExpense"
    assert by_year["FY2024"].sources["interest"] == "InterestExpenseNonoperating"
    print("Per-year resolution checks passed.")


def _thin_equity_checks():
    """Buyback-driven near-zero equity: show the number, refuse to grade it."""
    from sec_ratios import grade

    thin = analyze(build("Buyback Extreme Inc", {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 15_000_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 1_000_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 77_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 21_000_000_000)]),
        "DepreciationDepletionAndAmortization": usd([dur("2024-01-01", "2024-12-31", 3_000_000_000)]),
        "InterestExpense": usd([dur("2024-01-01", "2024-12-31", 1_800_000_000)]),
        "LongTermDebtNoncurrent": usd([inst("2024-12-31", 45_000_000_000)]),
    })).years[0]

    # 1,500% ROE and 77x D/E: printed, but ungraded so they take no colour.
    assert thin.ratios["Return on equity"].endswith("n/m"), thin.ratios
    assert thin.values["Return on equity"] is None
    assert grade("Return on equity", thin.values["Return on equity"]) is None
    assert thin.ratios["Debt / equity"].endswith("n/m"), thin.ratios
    assert thin.values["Debt / equity"] is None
    assert any("near zero" in f for f in thin.flags), thin.flags

    # Leverage against earnings still works and still grades, since it does
    # not touch the equity line at all.
    assert thin.values["Debt / EBITDA"] is not None
    assert grade("Debt / EBITDA", thin.values["Debt / EBITDA"]) == "good"

    # A normal company is untouched by the guard.
    ok = analyze(healthy).years[-1]
    assert ok.ratios["Return on equity"] == "20.00%"
    assert grade("Return on equity", ok.values["Return on equity"]) == "good"
    print("Thin equity checks passed.")


_per_year_resolution_checks()
_thin_equity_checks()


def _derivation_checks():
    """Gaps reconstructed from other tagged figures, always labelled as such."""
    from sec_ratios import DERIVED

    # A bank: no Liabilities tag, no OperatingIncomeLoss, no combined D&A.
    # Everything needed to rebuild them is tagged, so all three should fill.
    sparse_bank = build("Derivable Bancorp", {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 12_000_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 90_000_000_000)]),
        "Assets": usd([inst("2024-12-31", 900_000_000_000)]),
        "InterestExpense": usd([dur("2024-01-01", "2024-12-31", 20_000_000_000)]),
        # Pretax income, not operating income.
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest":
            usd([dur("2024-01-01", "2024-12-31", 15_000_000_000)]),
        # Depreciation and amortisation tagged separately.
        "Depreciation": usd([dur("2024-01-01", "2024-12-31", 800_000_000)]),
        "AmortizationOfIntangibleAssets": usd([dur("2024-01-01", "2024-12-31", 200_000_000)]),
        "ShortTermBorrowings": usd([inst("2024-12-31", 40_000_000_000)]),
    })
    y = analyze(sparse_bank).years[0]

    assert y.inputs["total_liabilities"] == 810_000_000_000, y.inputs
    assert y.sources["total_liabilities"].startswith(DERIVED)

    # EBIT is pretax PLUS interest -- using pretax alone understates coverage.
    assert y.inputs["ebit"] == 35_000_000_000, y.inputs["ebit"]
    assert "pretax" in y.sources["ebit"]
    assert y.ratios["Interest coverage"] == "1.75x", y.ratios

    assert y.inputs["da"] == 1_000_000_000, y.inputs["da"]
    assert "depreciation plus amortisation" in y.sources["da"]

    assert any("reconstructed from other figures" in f for f in y.flags), y.flags
    assert not y.missing() or "current_assets" in y.missing()

    # Derivations must not fire when the real tag is present.
    plain = analyze(healthy).years[-1]
    for key in ("total_liabilities", "ebit", "da"):
        assert not plain.sources[key].startswith(DERIVED), (key, plain.sources[key])
    assert not any("reconstructed" in f for f in plain.flags)

    # Equity from assets less liabilities, the other direction of the identity.
    no_equity = analyze(build("No Equity Tag Co", {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 1_000_000_000)]),
        "Assets": usd([inst("2024-12-31", 10_000_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 6_000_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 1_500_000_000)]),
    })).years[0]
    assert no_equity.inputs["equity"] == 4_000_000_000, no_equity.inputs
    assert no_equity.ratios["Return on equity"] == "25.00%", no_equity.ratios

    # Current liabilities from total less non-current.
    split = analyze(build("Partial Split Co", {
        "NetIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 500_000_000)]),
        "StockholdersEquity": usd([inst("2024-12-31", 3_000_000_000)]),
        "Liabilities": usd([inst("2024-12-31", 5_000_000_000)]),
        "LiabilitiesNoncurrent": usd([inst("2024-12-31", 3_500_000_000)]),
        "AssetsCurrent": usd([inst("2024-12-31", 2_250_000_000)]),
        "OperatingIncomeLoss": usd([dur("2024-01-01", "2024-12-31", 700_000_000)]),
    })).years[0]
    assert split.inputs["current_liabilities"] == 1_500_000_000, split.inputs
    assert split.ratios["Current ratio"] == "1.50x", split.ratios

    print("Derivation checks passed.")


_derivation_checks()
