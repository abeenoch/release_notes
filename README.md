# Release Notes

Automatically generate beautiful, AI-powered changelogs for your GitHub repositories. Supports multiple LLM providers and notification channels.

## Features

- **Multiple LLM Providers:** OpenAI, Anthropic, Groq, OpenRouter, Ollama (local), or commit-based mode (free, no API key)
- **GitHub Integration:** OAuth login, sync repos, auto-create webhooks for tag-based changelogs
- **Selective Repo Management:** Choose which repos to enable changelogs for — the rest stay synced but inactive
- **Notifications:** Deliver changelogs via SMTP email, SendGrid, or Slack webhooks
- **Dashboard:** Overview of repos, changelog history, and generation status
- **Background Processing:** Changelog generation runs asynchronously — no waiting

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy (async) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | React + Vite + Tailwind (pre-built in `frontend/dist/`) |
| Auth | GitHub OAuth + JWT |

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js (only if rebuilding the frontend — the built version is included)

### 1. Clone & Setup

```bash
git clone <repo-url>
cd auto-changelog

# Backend virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment config
cp .env.example .env
```

### 2. Configure GitHub OAuth (Required for Login)

1. Go to https://github.com/settings/developers
2. Click **"New OAuth App"**
3. Set **Authorization callback URL** to `http://localhost:8003/login`
4. Copy `Client ID` and `Client Secret` into `backend/.env`:
   ```env
   GITHUB_CLIENT_ID=your_client_id
   GITHUB_CLIENT_SECRET=your_client_secret
   ```

### 3. Start the Server

```bash
cd backend
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8003
```

Open http://localhost:8003 in your browser.

### 4. Generate a Changelog

1. Click **"Sync from GitHub"**
2. Select repos you want to enable → Click **"Import Selected"**
3. If you don't configure an LLM provider, the **commit-based mode** (free) is used automatically — it parses conventional commit messages
4. Click a repo name → **"Generate Now"**
## Configuration

### LLM Providers

Configured through the UI at **LLM Config** tab. Add one or more providers:

| Provider | Default Model | Requires API Key |
|----------|---------------|-----------------|
| Commit-based (free) | — | No |
| OpenAI | gpt-4o | Yes |
| Anthropic | claude-sonnet-4-20250514 | Yes |
| Groq | mixtral-8x7b-32768 | Yes |
| OpenRouter | anthropic/claude-3.5-sonnet | Yes |
| Ollama | llama3.3 (localhost:11434) | No |

### Notifications

Configured through the **Notifications** tab. Options:

- **SMTP** — Any SMTP server (Gmail, Outlook, etc.)
- **SendGrid** — SendGrid email API
- **Slack** — Webhook URL + channel

### Webhooks (Auto-Generation on Tag)

When you enable a repo, the backend creates a webhook pointing to:

```
http://YOUR_SERVER_IP:8003/api/webhook
```

The webhook fires on new tag creation, automatically queuing changelog generation.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEBUG` | No | Enable debug mode (`true`/`false`) |
| `SECRET_KEY` | Yes (prod) | JWT signing key |
| `DATABASE_URL` | No | Default: SQLite (`sqlite+aiosqlite:///./data/app.db`) |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth App client secret |
| `GITHUB_WEBHOOK_SECRET` | No | Secret for webhook HMAC verification |
| `JWT_EXPIRE_MINUTES` | No | Token expiry (default: 1440 = 24h) |
| `ENCRYPTION_KEY` | No | Fernet key for API key encryption at rest |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

## API Endpoints

### Auth
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/github` | Exchange OAuth code for JWT |
| GET | `/api/auth/me` | Get current user profile |

### Repositories
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/repos/` | List imported repos |
| POST | `/api/repos/sync` | Save all GitHub repos to DB (inactive) |
| POST | `/api/repos/preview` | Preview all GitHub repos (no save) |
| POST | `/api/repos/import` | Import selected repos as active |
| PATCH | `/api/repos/{id}/toggle` | Toggle repo active state |
| DELETE | `/api/repos/{id}` | Remove a repo |

### Changelogs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/changelogs/configs` | List LLM configs |
| POST | `/api/changelogs/configs` | Create LLM config |
| DELETE | `/api/changelogs/configs/{id}` | Delete LLM config |
| POST | `/api/changelogs/generate` | Trigger changelog generation |
| GET | `/api/changelogs/` | List changelogs |
| GET | `/api/changelogs/{id}` | Get changelog detail |

### Notifications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/notify/configs` | List notification configs |
| POST | `/api/notify/configs` | Create notification config |
| DELETE | `/api/notify/configs/{id}` | Delete notification config |

### Webhook
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/webhook` | Receive GitHub webhook events |

## Project Structure

```
auto-changelog/
├── backend/
│   ├── app/
│   │   ├── api/          # Route handlers (auth, repos, changelogs, etc.)
│   │   ├── core/         # Dependencies, security, errors
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── services/     # Business logic (auth, github, git_ops, llm, notify)
│   │   ├── tasks/        # Background worker
│   │   ├── config.py     # Settings from env
│   │   ├── database.py   # SQLAlchemy engine + session
│   │   └── main.py       # FastAPI app
│   ├── data/             # SQLite DB + cloned repos
│   ├── tests/
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── dist/             # Pre-built React app (served by backend)
│   │   ├── assets/
│   │   └── index.html
│   ├── index.html        # Source HTML (for rebuilding)
│   └── node_modules/
├── .gitignore
└── README.md
```

## License

MIT
