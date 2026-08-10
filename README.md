# credit-screen

**Try it: [credit-ratios.streamlit.app](https://credit-ratios.streamlit.app)**

Type a company name. Get twelve numbers that tell you whether it can pay back
what it owes.

*Free hosting, so the site sleeps when nobody is using it. If you land on a
"wake this app up" screen, click it and give it about 30 seconds.*


---

## What problem this solves

Every US public company files an annual report with the government. The numbers
a lender cares about are in there, buried in 200 pages, and comparing five
companies means five afternoons.

This pulls them automatically and lays three years side by side.

## What it shows

**Liquidity — can it pay this year's bills?**

| | The question it answers |
|---|---|
| Current ratio | Can it cover the bills due this year with what it has on hand? |
| Quick ratio | The same, ignoring stock that still has to be sold |

**Leverage — how much does it owe, and can it service it?**

| | |
|---|---|
| Debt / equity | How much is funded by borrowing versus by the owners? |
| Debt / assets | What share of everything it owns is funded by what it owes? |
| Debt / EBITDA | How many years of earnings would clear the debt? |
| Debt / EBITDA (lease-adjusted) | The same, counting long store and aircraft leases as debt |
| Interest coverage | How many times over can it cover the interest? |

**Profitability — is the business any good?**

| | |
|---|---|
| Net profit margin | How much of each sales dollar is left as profit? |
| EBITDA margin | The same, before interest, tax and wear on its assets |
| Return on assets | How much profit does each dollar of assets produce? |
| Return on equity | How much profit does each dollar of owner money produce? |

**Efficiency**

| | |
|---|---|
| Asset turnover | How much revenue does each dollar of assets generate? |

Green is healthy, amber means keep an eye on it, red means something worth
understanding. White means the number **does not apply** — a different thing
from bad, and the tool is careful about that difference.

Every ratio also gets a plain sentence using the company's own figures, so you
never have to translate a number into meaning yourself:

> *For every $1 the owners have in, the company owes $1.30 to others.*
>
> *Earnings cover the interest bill 8.8 times over. Profits could fall about
> 89% before interest stopped being covered.*

## Where the numbers come from

Not from scraping the report. When a company files, it also submits every
figure with a standard label attached, and the government publishes all of it.
So the tool looks up labels rather than reading documents. Fast, and nothing is
guessed.

## Why this is harder than dividing two numbers

Anyone can write the formulas. Real filings are messier than the textbook, and
most of the work here is handling that.

**Some ratios are meaningless for some companies, and printing them would
mislead you.** Home Depot has bought back so much of its own stock that the
owners' stake is nearly zero on paper. Divide by nearly zero and return on
equity comes out at 1,450%. That is arithmetically correct and completely
useless, so the tool shows the figure but refuses to call it good.

**Banks are not just another industry.** For a bank, interest paid to
depositors is the cost of the product, not a financing charge — so EBITDA is
neither reported nor meaningful, and leverage above 10x is the business model
rather than distress. The tool spots a bank from the way it files and stops
scoring the ratios that do not transfer, saying which measures lenders are
actually judged on instead. Most free screeners will happily print a bank's
Debt/EBITDA and let you draw the wrong conclusion.

**Asset turnover is never scored.** A power utility runs near 0.3 and a
supermarket near 3.0, both perfectly healthy. Any universal threshold would
just be reporting the industry back to you dressed up as a verdict. The number
is shown; the trend is what matters.

**Companies label the same thing differently.** Depreciation has at least three
common labels. Nike does not label its interest expense at all. For each figure
the tool tries a list of possible labels until one works — and it tries again
for every year, because filers switch labels between years.

**It rebuilds what is missing.** If total liabilities are not labelled but
assets and equity are, it subtracts. If operating profit is missing, it adds
interest back to pretax income. Every rebuilt figure is marked as rebuilt.

**And when all else fails, you type it in.** Anything the tool cannot find, you
enter yourself from the report. Those get flagged too. A number you typed is
never presented as though the company filed it.

That last point is the whole idea. The tool never quietly makes something up.

## What it cannot do

- **US companies only.** Nestlé, Toyota and DHL file with their own countries,
  not the SEC, so they will not come up.
- **Annual reports only.** No quarterly figures.
- **The thresholds are rough.** What counts as too much debt depends heavily on
  the industry. Treat a colour as a reason to look closer, not a verdict.
- **It is a screening tool, not an analysis.** It tells you where to look. The
  filing tells you what is actually going on.

## Running it yourself

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your@email.com"
streamlit run app.py
```

The government requires that you identify yourself when requesting data — that
is all `SEC_USER_AGENT` is for. No account or API key needed.

To check the logic with no internet at all:

```bash
python test_offline.py
```

That runs eleven groups of checks against made-up companies built to trigger
every awkward case — negative equity, a bank, a filer that switches labels
between years, one that tags almost nothing — and confirms each is handled.

## What is in here

| File | What it does |
|---|---|
| `app.py` | The website |
| `sec_ratios.py` | Fetching, labels, ratios, and all the special cases |
| `assistant.py` | Optional AI chat that answers questions about the numbers |
| `run.py` | Prints the same table in a terminal, for testing |
| `test_offline.py` | Checks the logic with no internet needed |
| `prototype.html` | A standalone design mockup with sample data |

---

Built as a portfolio project. The interesting part is not the formulas — it is
everything the tool does when a filing does not behave.
