# credit-screen

**Try it: [credit-ratios.streamlit.app](https://credit-ratios.streamlit.app)**

Type a company name. Get five numbers that tell you whether it can pay back
what it owes.

*The site is on free hosting and sleeps when nobody is using it. If you get a
"wake this app up" screen, click it and give it about 30 seconds.*

<!-- Drop a screenshot here: drag an image into GitHub's editor and it uploads. -->

---

## What problem this solves

Every US public company has to file an annual report with the government. The
numbers a lender cares about are in there, but they are buried in a 200-page
document, and reading five companies means five afternoons.

This pulls those numbers automatically and lays them out side by side.

## What the five numbers mean

Plain English, no finance background needed:

| | The question it answers |
|---|---|
| **Return on equity** | For every dollar the owners put in, how much profit comes back? |
| **Current ratio** | Can the company pay the bills due this year with what it has on hand? |
| **Debt / equity** | How much of the company is funded by borrowing versus by its owners? |
| **Interest coverage** | How many times over can it pay the interest on its loans? |
| **Debt / EBITDA** | If it put every dollar of earnings toward the debt, how many years to clear it? |

Green means healthy, amber means keep an eye on it, red means there is a
problem worth understanding. White means the number does not apply — which is a
different thing from bad, and the tool is careful about the difference.

## Where the numbers come from

Not from scraping the report. When a company files, it also submits every
figure with a standard label attached, and the government publishes all of it.
So the tool looks up labels instead of reading documents. Fast, and nothing is
guessed.

## Why this is harder than dividing two numbers

Anyone can write the formulas. Real filings are messier than the textbook, and
most of the work here is handling that:

**Sometimes a ratio is meaningless and printing it would mislead you.** Home
Depot has bought back so much of its own stock that the owners' stake is almost
zero on paper. Divide by almost zero and return on equity comes out at 1,450%.
That is arithmetically correct and completely useless. The tool shows the
figure but refuses to call it good.

**Banks do not have a "current ratio."** They organise their balance sheet
differently, so there is nothing to compute. The tool says so instead of
showing a zero.

**Companies label the same thing differently.** Depreciation has at least three
common labels. Nike does not label its interest expense at all. For each figure
the tool tries a list of possible labels until one works.

**Sometimes it can rebuild what is missing.** If total liabilities are not
labelled but assets and equity are, it subtracts. Every rebuilt figure is
marked as rebuilt, so you always know what came from the filing and what came
from arithmetic.

**And when all else fails, you can type it in.** Anything the tool cannot find,
you enter yourself from the report. Those get flagged too. A number you typed
is never presented as though the company filed it.

That last point is the whole idea. The tool never quietly makes something up.

## What it cannot do

- **US companies only.** Nestlé, Toyota and DHL file with their own countries,
  not the SEC, so they will not come up.
- **Annual reports only.** No quarterly figures.
- **The colour thresholds are rough.** What counts as too much debt depends
  heavily on the industry — a utility and a software company are not comparable.
  Treat a colour as a reason to look closer, not a verdict.
- **It is a screening tool, not an analysis.** It tells you where to look. The
  filing tells you what is actually going on.

## Running it yourself

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your@email.com"
streamlit run app.py
```

The government requires that you say who you are when requesting data — that is
what `SEC_USER_AGENT` is for. No account or API key needed.

To check the logic without any internet:

```bash
python test_offline.py
```

That runs made-up companies built to trigger every awkward case, and confirms
the tool handles each one.

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
