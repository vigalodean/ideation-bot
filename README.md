# IDP Ideation Bot (@ideated_bot)

A Telegram bot that helps students brainstorm ideas for their 12-week app prototype projects in the IDP course. Every idea is based on a real, recent Singapore news story, so students have something concrete to start from.

## About the project

I built this bot as a Teaching Assistant for the IDP course. Students pick a news theme. The bot then scrapes recent articles from that section of **The Straits Times** and uses the **Anthropic Claude API** to turn each one into a new, evidence-based app idea for Singapore.

The bot was run locally for an in-class idea generation exercise. About 80 students across 2 sections used it, and it helped them come up with more project ideas. The course instructor later adopted it for Week 1 project proposals.

### How it works

1. A student sends `/start` and picks one of eight news themes:
   - 🌿 Environment & Sustainability
   - 🧠 Health & Wellness
   - 📚 Parenting & Education
   - 🎨 Community, Arts & Heritage
   - 🚌 Urban Mobility & Transport
   - 🏠 Housing & Estate Living
   - 💼 Jobs & Economy
   - 🛡️ Scam & Safety Prevention
2. The bot picks up to **five** articles at random from that Straits Times section, keeping only those **published within the last year**.
3. Claude turns each article into an app idea with:
   - 📌 **Big-picture overview** of the problem and the proposed solution
   - 🧭 **User journeys**: one smooth path and one hard path, written as user stories
   - 👥 **Potential target users** in Singapore
   - 📰 **A clickable citation** linking back to the source article
4. Students move around with the inline theme buttons and the **🔙 Back to Main Menu** button.

### Bot commands

| Command  | Description                      |
| -------- | -------------------------------- |
| `/start` | Show the theme selection menu    |
| `/help`  | Explain how to use the bot       |
| `/end`   | End the session with a goodbye   |

### Project structure

| File                | Purpose                                                                                     |
| ------------------- | ------------------------------------------------------------------------------------------- |
| `main.py`           | Entry point. Sets up the Telegram bot, commands and inline keyboards                         |
| `st_scraper.py`     | Scrapes Straits Times section pages and articles, and filters for the last year              |
| `idea_generator.py` | Builds the prompt, calls Claude with a JSON-schema response, and formats the Telegram messages |
| `database.py`       | Caches generated ideas per article URL in SQLite (`ideas.db`), so an article is never billed twice |
| `rate_limiter.py`   | Sets per-minute and daily limits on Claude API calls to control spending                     |

### Tech stack

- Python 3.10+
- [python-telegram-bot](https://python-telegram-bot.org/)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) (Claude Haiku 4.5)
- `requests` + BeautifulSoup for web scraping
- SQLite for caching ideas

## Running locally

### Prerequisites

- **Python 3.10 or newer**
- A **Telegram bot token**: message [@BotFather](https://t.me/BotFather) on Telegram, send `/newbot`, and follow the prompts
- An **Anthropic API key** from the [Anthropic Console](https://console.anthropic.com/)

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd ideatime
```

### 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy the example file to `.env`:

```bash
# macOS / Linux
cp .env.example .env

# Windows (PowerShell)
Copy-Item .env.example .env
```

Then open `.env` and fill in your credentials:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional: limits on Claude API calls (defaults shown)
# CLAUDE_MAX_CALLS_PER_MINUTE=10
# CLAUDE_MAX_CALLS_PER_DAY=200
```

> ⚠️ `.env` is listed in `.gitignore`. Never commit your real tokens.

### 5. Start the bot

```bash
python main.py
```

If it starts correctly, you will see:

```
🚀 Ideation Bot (@ideated_bot) is running with LIVE Straits Times Web Scraping!
Press Ctrl+C to stop the bot.
```

Open your bot in Telegram and send `/start`. The bot only responds while `main.py` is running, so keep the terminal open. Press **Ctrl+C** to stop it.

### Files created at runtime

Both files are git-ignored. You can delete them safely to reset state.

- `ideas.db`: SQLite cache of generated ideas
- `rate_limit_state.json`: today's count of Claude API calls

## Troubleshooting

| Symptom | Likely cause / fix |
| ------- | ------------------ |
| `ERROR: TELEGRAM_BOT_TOKEN is not configured.` | `.env` is missing, or the token is still the placeholder value. |
| "Could not retrieve live Straits Times articles" | The Straits Times site could not be reached, or its page layout changed. Try again or pick another theme. |
| "Claude couldn't generate any app ideas right now." | `ANTHROPIC_API_KEY` is missing or invalid, or the daily call limit (`CLAUDE_MAX_CALLS_PER_DAY`) has been reached. Check the terminal logs for details. |
| Ideas take a while to appear | Normal. The bot scrapes up to five articles and makes one Claude call per article, so a response can take about a minute. |
