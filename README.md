# MailPilot

Email orchestrator: reads Gmail, summarizes/classifies with an LLM, notifies via Telegram.

See [ROADMAP.md](ROADMAP.md) for the version plan.

## Setup

1. Google Cloud Console: create a project, enable Gmail API, configure OAuth consent screen, create an OAuth Client ID (Desktop app), download it as `credentials.json` in the project root.
2. ```bash
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. `python scripts/authenticate.py` — first run opens a browser to log in, later runs reuse `token.json`.

Activate the venv (`source .venv/bin/activate`) each time you open a new terminal.
