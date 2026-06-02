# Expired Domain Agent

> AI-powered bot that discovers high-value expired .com domains daily, scores them with Gemini AI, and emails you a ranked Excel report.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://python.org)
[![Gemini](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-orange)](https://ai.google.dev)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## How It Works

```
Scrape ExpiredDomains.net
        |
    Filter (.com, 4-12 chars, available, no numbers/specials)
        |
    AI scores each domain (brandability, resale, pronounceability, memorability)
        |
    Weighted formula → Top 20 ranking
        |
    Excel report → emailed to you
```

Every domain is evaluated on 5 dimensions by **Gemini 2.5 Flash** (or GPT-4o-mini as fallback), then scored with a weighted formula:

| Criterion | Weight |
|-----------|--------|
| Brandability (AI) | 30% |
| Resale Potential (AI) | 25% |
| Length Score | 15% |
| Registered TLDs | 10% |
| Pronounceability (AI) | 10% |
| Memorability (AI) | 10% |

---

## Features

- **Daily automation** — scraper runs at your configured hour via `--schedule` or Windows Task Scheduler
- **AI scoring** — domains rated by Gemini 2.5 Flash (free tier) on 5 metrics
- **Smart filtering** — .com only, 4-12 chars, no numbers/specials, max 2 words, Reg >= 3
- **Excel reports** — formatted with color coding, frozen headers, auto-filters
- **Email delivery** — report delivered to your inbox daily via Gmail SMTP
- **Feedback learning** — rate domains (BUY/GOOD/BAD/SKIP) and the AI adapts to your taste
- **Dual provider** — Gemini by default, OpenAI as fallback (just change one env var)
- **SQLite persistence** — all domains, reports, and feedback stored locally
- **Error resilience** — retry logic with exponential backoff on all external calls

---

## Quick Start

### Prerequisites

- Python 3.12+
- Google Chrome or Chromium (for Playwright)
- [ExpiredDomains.net](https://expireddomains.net) member account
- [Gemini API key](https://aistudio.google.com/apikey) (free tier)
- Gmail account with an [App Password](https://myaccount.google.com/apppasswords)

### Setup

```powershell
# Clone & enter
git clone https://github.com/walidchajari/expired-domain-agent.git
cd expired-domain-agent

# Virtual environment
python -m venv venv
.\venv\Scripts\Activate

# Dependencies
pip install -r requirements.txt
playwright install chromium

# Configure credentials
cp .env.example .env
notepad .env
```

### Run

```powershell
# One-time manual run
python run.py

# Daily scheduled execution
python run.py --schedule

# Rate domains to train the AI
python run.py --feedback BUY reflyme.com
python run.py --feedback GOOD trykiki.com
python run.py --feedback BAD ghostbuskers.com
python run.py --feedback SKIP enoughfluff.com
```

---

## Project Structure

```
expired-domain-agent/
├── run.py                 # Orchestrator & CLI (--schedule, --feedback)
├── config.py              # Environment-based configuration
├── scraper.py             # Playwright scraper for ExpiredDomains.net
├── ai_scoring.py          # Gemini/OpenAI scoring engine
├── report_generator.py    # Excel report builder (openpyxl)
├── email_sender.py        # SMTP delivery via Gmail
├── database.py            # SQLite ORM (domains, feedback, reports)
├── feedback_learner.py    # Preference learning system
├── requirements.txt       # Python dependencies
├── .env.example           # Configuration template
├── .gitignore
├── reports/               # Generated Excel files
└── data/                  # SQLite DB & logs
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

| Variable | Description |
|----------|-------------|
| `EXPIRED_USERNAME` | ExpiredDomains.net email |
| `EXPIRED_PASSWORD` | ExpiredDomains.net password |
| `AI_PROVIDER` | `gemini` (default) or `openai` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SMTP_USERNAME` | Your Gmail address |
| `SMTP_PASSWORD` | Gmail App Password (16 chars) |
| `EMAIL_TO` | Report recipient |
| `MAX_DOMAINS_TO_ANALYZE` | Domains to score per run (default: 50) |
| `TOP_N_DOMAINS` | Report size (default: 20) |
| `DAILY_RUN_HOUR` | Hour for scheduler (0-23) |

---

## Excel Report

Generated as `Top20Domains_YYYY_MM_DD.xlsx` with:

- Bold white-on-blue headers
- Auto-sized columns
- Color-coded scores: green > 85, yellow 70-85, red < 70
- Frozen header row
- Auto-filters enabled

---

## Feedback Learning

Every rating updates your preference profile in SQLite. The system learns which domain patterns you like and boosts scores for similar domains in future runs.

```powershell
# View your current preference profile
python run.py --feedback

# Rate domains
python run.py --feedback BUY trykiki.com
python run.py --feedback GOOD pergovia.com
python run.py --feedback BAD addtochart.com
```

---

## Production Deployment

| Environment | Method |
|-------------|--------|
| **Windows** | Task Scheduler (daily trigger) |
| **Linux** | systemd timer + service |
| **Docker** | Build image with cron |
| **AWS** | Lambda + EventBridge |

---

## License

MIT
