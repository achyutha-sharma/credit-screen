# Putting this online

Two URLs, on purpose:

| | What it is | Loads |
|---|---|---|
| **GitHub Pages** | `docs/index.html` — the static prototype, sample data | Instantly, always |
| **Streamlit Cloud** | `app.py` — the real tool against live SEC filings | Sleeps after 12 quiet hours |

Community Cloud hibernates apps with no traffic for 12 hours; the next visitor
gets a "wake this app up" page instead of your work. A recruiter clicking a
link at 9pm should not land on that. So the Pages URL is the front door and it
links through to the live app.

---

## 1. Install the tools

**Git** — `git --version`. If it is missing: macOS installs it when you run
`xcode-select --install`; Windows, download from git-scm.com.

**GitHub account** — github.com, free. Verify the email; Pages will not publish
until you do.

Tell git who you are (once per machine):

```bash
git config --global user.name "Your Name"
git config --global user.email "you@email.com"
```

---

## 2. Check nothing secret is about to be committed

The single step worth being careful about. Leaked API keys get scraped from
public repos within minutes.

```bash
cd sec-ratio-tool
git init
git add .
git status
```

Read the list. You should see the `.py` files, `README.md`, `requirements.txt`,
`.streamlit/config.toml`, `prototype.html`, `.gitignore`.

You must **not** see `.env`, `secrets.toml`, `.sec_cache/`, or `.venv/`. If any
appear, stop and check `.gitignore` is present before continuing.

```bash
git commit -m "Credit ratio screening from SEC XBRL data"
```

---

## 3. Push to GitHub

On github.com click **New repository**. Name it `sec-credit-ratios`. Public.
Do **not** tick "add a README" — you have one.

Copy the two commands GitHub shows under "push an existing repository":

```bash
git remote add origin https://github.com/YOUR-USERNAME/sec-credit-ratios.git
git branch -M main
git push -u origin main
```

If it asks for a password, it wants a personal access token, not your account
password: GitHub → Settings → Developer settings → Personal access tokens →
Tokens (classic) → Generate, with the `repo` scope. Paste that as the password.

---

## 4. Publish the static prototype

```bash
mkdir -p docs
cp prototype.html docs/index.html
git add docs && git commit -m "Publish prototype to Pages" && git push
```

Then on GitHub: **Settings → Pages → Source: Deploy from a branch → main →
/docs → Save.**

Live in a minute or two at:

```
https://YOUR-USERNAME.github.io/sec-credit-ratios/
```

Static files only — no Python — which is why it never sleeps and costs nothing.

---

## 5. Deploy the live app

Go to **share.streamlit.io**, sign in with GitHub, **Create app** → pick the
repo, branch `main`, main file `app.py`.

Before clicking Deploy, open **Advanced settings → Secrets** and paste:

```toml
SEC_USER_AGENT = "Your Name you@email.com"
ANTHROPIC_API_KEY = "sk-ant-..."
```

TOML format, quoted strings. Streamlit exposes these as environment variables,
which is exactly what `sec_ratios.py` and `assistant.py` read — no code change
between your laptop and production.

First build takes a few minutes. Then set a readable subdomain under
**Settings → General**, e.g. `credit-screen.streamlit.app`. Custom subdomains
are supported; your own top-level domain is not, on the free tier.

---

## 6. Link the two together

Edit `prototype.html`, find `YOUR-APP.streamlit.app` in the masthead, replace
it with your real Streamlit URL. Then:

```bash
cp prototype.html docs/index.html
git add -A && git commit -m "Link prototype to live app" && git push
```

Pages updates in about a minute. Streamlit redeploys automatically on every
push to `main` — no separate deploy step.

---

## 7. Sanity check before sharing

- [ ] Pages URL loads instantly in a private window
- [ ] "Open the live app" points at the right place
- [ ] Live app returns a real table for NKE
- [ ] Assistant answers a question
- [ ] Repo contains no key: search it on GitHub for `sk-ant`
- [ ] README opens with the edge cases, not a feature list

---

## Where to put it

**Resume** — one line under projects, with the Pages link:
*Credit ratio screening tool — parses SEC XBRL filings into leverage and
coverage metrics, handling negative equity, unclassified bank balance sheets,
and untagged line items. Python, Streamlit.*

**LinkedIn** — Featured section takes a link and renders a preview card.

**Interviews** — send the Pages URL. It loads instantly, shows the design, and
the live app is one click away if they want to try a real company.

---

## Costs

Everything above is free. GitHub Pages and Community Cloud both cost nothing
for public repos, and SEC's API has no key or fee. The only spend is Anthropic
API usage for the assistant, which is fractions of a cent per question at these
context sizes — and the tool runs fine without a key, with just the chat panel
disabled.

## If you outgrow the free tier

Only worth it if the sleeping genuinely bothers you. Paid always-on hosting for
a small Python app runs about $5–10/month on the usual platforms, and that is
the tier where your own domain becomes possible. For a portfolio piece, the
free setup is the right answer — check current pricing before committing, since
these plans change.
