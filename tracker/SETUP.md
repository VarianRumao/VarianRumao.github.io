# Job Tracker — 100% free setup

A private dashboard at **varianrumao.com/tracker** that auto-ingests your job-application
emails from Gmail. No AWS, no credit card, no AI billing. The whole thing runs on:

- **GitHub Actions** (free, unlimited minutes on public repos) — pulls Gmail hourly,
  classifies with regex, and commits an **encrypted** data file back to this repo.
- **GitHub Pages** (already hosting your site) — serves the page.
- **Your browser** — decrypts the data with a passphrase you type. The committed file is
  ciphertext (AES-256-GCM), so even though this repo is public, the data is private.

```
GitHub Actions (hourly cron)
   │  reads Gmail via refresh token (a GitHub Secret)
   │  classify (regex) → upsert → encrypt with TRACKER_PASSPHRASE
   ▼
data/applications.enc.json   ← ciphertext, committed to the repo
   ▲
   │  fetch + decrypt in the browser (Web Crypto)
varianrumao.com/tracker      ← asks for the passphrase, renders the dashboard
```

---

## What's already built

| File | Purpose |
|------|---------|
| `tracker/index.html` | The dashboard. Passphrase gate → decrypts → renders stats + table. |
| `scripts/ingest.py` | Gmail pull → classify → upsert → encrypt → write data file. |
| `scripts/classify.py` | Free regex classifier (status / company / role / source). |
| `scripts/crypto_util.py` | AES-256-GCM envelope, byte-compatible with the browser. |
| `scripts/get_gmail_token.py` | One-time local script to mint a Gmail refresh token. |
| `.github/workflows/ingest.yml` | Hourly schedule + manual "Run workflow" button. |
| `data/applications.enc.json` | **Demo** data right now (passphrase `demo`). Real ingest overwrites it. |

You can already preview it: visit `/tracker`, enter **`demo`**, and you'll see sample data.

---

## Finish it — 3 steps only you can do

### Step 1 — Get a Gmail refresh token (~5 min, once)

1. [Google Cloud Console](https://console.cloud.google.com/) → create a project.
2. **APIs & Services → Library →** enable **Gmail API**.
3. **OAuth consent screen** → External → add yourself as a **Test user**.
4. **Credentials → Create credentials → OAuth client ID → Desktop app** → download the JSON.
5. Save it as `scripts/client_secret.json` (already git-ignored — it won't be committed).
6. Run locally:
   ```bash
   pip install google-auth-oauthlib
   python scripts/get_gmail_token.py
   ```
   A browser opens; approve. It prints `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`,
   `GMAIL_REFRESH_TOKEN`.

### Step 2 — Add 4 GitHub Secrets

In this repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add all four:

| Secret | Value |
|--------|-------|
| `GMAIL_CLIENT_ID` | from step 1 |
| `GMAIL_CLIENT_SECRET` | from step 1 |
| `GMAIL_REFRESH_TOKEN` | from step 1 |
| `TRACKER_PASSPHRASE` | **a strong passphrase you choose** — this is what you'll type on the page |

> The passphrase is the encryption key. If you change it later, re-run the ingest so the
> data file is re-encrypted with the new one.

### Step 3 — Run the first ingest

- Push these files to GitHub (if not already).
- **Actions tab → "Job tracker ingest" → Run workflow.** (After this it runs hourly on its own.)
- When it finishes it commits a fresh `data/applications.enc.json` built from your inbox.
- Visit `varianrumao.com/tracker`, enter your `TRACKER_PASSPHRASE`, and your real data appears.

That's it — fully automatic from then on.

---

## Notes

- **Gmail scope** is `gmail.modify` (read + apply the `Tracker-Processed` label). It cannot
  send or delete mail. The label makes ingestion idempotent — each email is counted once.
- **De-dup:** rows are keyed `account` + normalized `company#role`. Status only ever climbs
  `Awaiting → Viewed → Rejected → Interview → Offer`, so a late email can't bury an interview.
- **Tuning:** edit `GMAIL_QUERY` / `PROCESSED_LABEL` at the top of `scripts/ingest.py`, or
  the cron in `.github/workflows/ingest.yml` (e.g. `0 */6 * * *` for every 6 hours).
- **The page is `noindex`** and only reachable if someone knows the URL — and useless without
  the passphrase. For an extra edge-gate (hide the page itself), Cloudflare Access free tier
  works, but it's optional; the data is already encrypted at rest.
- **Cost:** $0. Public-repo Actions minutes are free; Pages is free; no third-party APIs are
  metered (Gmail API is free, classification is local regex).
