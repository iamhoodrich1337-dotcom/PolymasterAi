# POLYMASTER AI

Autonomous research and paper-trading platform for Polymarket.

**Live trading is LOCKED by default. This project performs paper trading only.**

## Quick Start (Local)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: DATABASE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_ID
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
