# ⚡ Ladder Bet Intelligence System

Automated daily bet analysis powered by **Claude Opus with Extended Thinking**.
Scans every fixture across EPL, Bundesliga, Serie A, La Liga, and NBA, scores each
opportunity, and produces a ranked Excel feed + live GitHub Pages dashboard.

---

## Architecture

```
GitHub Actions (daily @ 7am AEST)
        │
        ▼
scripts/generate_bets.py
  ├── Fetch fixtures + odds  ← The Odds API
  ├── Claude Opus analysis   ← Extended thinking (8,000 budget tokens)
  ├── Build Excel feed       ← 4-sheet workbook
  └── Update JSON + history
        │
        ▼
docs/data/
  ├── bets.json          ← Live dashboard feed
  ├── bets_YYYY-MM-DD.xlsx  ← Daily Excel download
  └── history.json       ← Rolling 90-day log
        │
        ▼
GitHub Pages → your-username.github.io/ladder-intelligence
```

---

## Setup (5 minutes)

### 1. Create the repo
```bash
git clone this repo
cd ladder-intelligence
git remote set-url origin https://github.com/YOUR_USERNAME/ladder-intelligence.git
git push -u origin main
```

### 2. Add GitHub Secrets
Go to **Settings → Secrets → Actions → New repository secret**

| Secret name       | Where to get it |
|-------------------|-----------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| `ODDS_API_KEY`      | https://the-odds-api.com (free tier: 500 req/month) |

### 3. Enable GitHub Pages
**Settings → Pages → Source: Deploy from branch → Branch: main → Folder: /docs**

Your dashboard will be live at:
`https://YOUR_USERNAME.github.io/REPO_NAME`

### 4. Enable GitHub Actions
**Actions tab → "I understand my workflows, go ahead and enable them"**

The workflow runs daily at 7am AEST (21:00 UTC).
Trigger manually any time via **Actions → Daily Bet Intelligence → Run workflow**.

---

## Excel Feed (4 sheets)

| Sheet | Contents |
|-------|----------|
| 🎯 Best Bets Today | Top TAKE/MONITOR picks, colour-coded |
| 📊 Full Analysis   | Every opportunity scored and ranked |
| 🔗 Parlay Builder  | Running combined odds for 2x targeting |
| 📈 Model Log       | Daily stats and best edge bet |

**Columns:** Verdict · Confidence · Edge ★★★★★ · Ladder Fit · Match · Sport · Market · Outcome · Odds · EV% · Kelly% · Reasoning · Risk Flags · Combo Partner

---

## Model Logic

Claude Opus evaluates each opportunity on:

- **Confidence (0–100%)** — probability the bet wins
- **Edge rating (1–5)** — how much value vs market price
- **Expected Value** — mathematical edge (+EV = good)
- **Kelly fraction** — optimal stake % of bankroll
- **Ladder Fit** — PERFECT / GOOD / MARGINAL / POOR (targets 1.90–2.15x)
- **Risk flags** — injury news, form concerns, variance warnings
- **Combo partner** — suggested second leg for parlay

**Verdict logic:**
- `TAKE` → high confidence + positive EV + good ladder fit
- `MONITOR` → promising but needs rechecking closer to game time
- `SKIP` → low confidence, negative EV, or high variance

---

## Customisation

**Change sports** — edit `SPORTS` list in `generate_bets.py`

**Change schedule** — edit cron in `.github/workflows/daily_bets.yml`

**Change reasoning depth** — adjust `budget_tokens` (higher = deeper thinking, slower)

**Add racing** — The Odds API covers some racing markets under `horse_racing_*`

---

## Security

- API keys stored only in GitHub Secrets — never in code
- No keys in any committed files
- GitHub Pages serves only the `docs/` folder (static HTML + JSON)
- The pipeline runs in isolated GitHub Actions runners

---

## Cost estimate

| Service | Cost |
|---------|------|
| Anthropic (Claude Opus) | ~$0.50–2.00/day depending on fixture count |
| The Odds API | Free tier (500 req/month) sufficient |
| GitHub Actions | Free (within public repo limits) |
| GitHub Pages | Free |
