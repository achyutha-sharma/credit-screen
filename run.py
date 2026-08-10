"""
Terminal runner. Prints the ratio table for a company, colour-coded.

Use this to test real filings. Debugging tag coverage in a terminal is far
faster than doing it through a web UI, and it is the same code path the app
uses -- if it looks right here, the app will show the same thing.

    python3 run.py NKE
    python3 run.py "home depot"
    python3 run.py --demo          # synthetic filings, no network needed
    python3 run.py NKE --raw       # also print the ten inputs and their tags
"""

import sys

from sec_ratios import (
    GOOD,
    WATCH,
    WEAK,
    SecClient,
    analyze,
    grade,
    inputs_table,
    to_table,
)

C = {
    GOOD: "\033[32m",
    WATCH: "\033[33m",
    WEAK: "\033[31m",
    "dim": "\033[90m",
    "bold": "\033[1m",
    "off": "\033[0m",
}


def paint(text: str, bucket: str | None, width: int) -> str:
    """Right-align, then colour. Padding first keeps columns aligned, since
    escape codes count as characters but take no visual space."""
    padded = text.rjust(width)
    if bucket:
        return f"{C[bucket]}{padded}{C['off']}"
    return f"{C['dim']}{padded}{C['off']}"


def show(analysis, raw: bool = False) -> None:
    years = sorted(analysis.years, key=lambda y: y.period_end)
    header, rows = to_table(analysis)
    w = 26

    print(f"\n{C['bold']}{analysis.entity}{C['off']}")
    print(f"{C['dim']}{years[0].label} - {years[-1].label}, Form 10-K{C['off']}\n")

    print("Ratio".ljust(28) + "".join(y.label.rjust(w) for y in years))
    print("-" * (28 + w * len(years)))
    for row in rows:
        name = row[0]
        cells = "".join(
            paint(row[i + 1], grade(name, y.values.get(name)), w)
            for i, y in enumerate(years)
        )
        print(name.ljust(28) + cells)

    if analysis.all_flags:
        print(f"\n{C['bold']}How to read this{C['off']}")
        for f in analysis.all_flags:
            print(f"  {C['dim']}-{C['off']} {f}")

    gaps = sorted({k for y in years for k in y.missing()})
    if gaps:
        print(
            f"\n{C[WATCH]}Not tagged:{C['off']} {', '.join(gaps)}"
            f"\n{C['dim']}Add these tags to the chains in sec_ratios.py, or type them"
            f" into the app.{C['off']}"
        )

    if raw:
        ih, ir = inputs_table(analysis)
        print(f"\n{C['bold']}Inputs ($ millions){C['off']}")
        print(ih[0].ljust(30) + "".join(h.rjust(16) for h in ih[1:-1]) + "   " + ih[-1])
        for r in ir:
            print(
                r[0].ljust(30)
                + "".join(c.rjust(16) for c in r[1:-1])
                + f"   {C['dim']}{r[-1]}{C['off']}"
            )


def main() -> None:
    args = [a for a in sys.argv[1:]]
    raw = "--raw" in args
    args = [a for a in args if not a.startswith("--")] or ["NKE"]

    if "--demo" in sys.argv:
        from test_offline import bank, healthy, negative_equity

        for payload in (healthy, negative_equity, bank):
            show(analyze(payload), raw=raw)
        return

    query = " ".join(args)
    client = SecClient()
    hits = client.search(query)
    if not hits:
        sys.exit(f"Nothing matches {query!r}.")
    if len(hits) > 1:
        print(f"{C['dim']}Matches:{C['off']}")
        for h in hits[:5]:
            print(f"  {h['ticker']:<8}{h['name']}")
        print(f"{C['dim']}Using the first.{C['off']}")

    company = hits[0]
    show(analyze(client.company_facts(company["cik"])), raw=raw)


if __name__ == "__main__":
    main()
