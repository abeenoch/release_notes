# Release Notes

Automatically generate beautiful, AI-powered changelogs for your GitHub repositories. Supports multiple LLM providers and notification channels.

## Features

- **Cinematic landing page + dark-branded login:** OAuth flow returns straight into the app (`/login`) — no page flashes, CSRF-protected with OAuth `state`
- **Multiple LLM Providers:** OpenAI, Anthropic, Groq, OpenRouter, Ollama (local), or commit-based mode (free, no API key)
- **GitHub Integration:** OAuth login, sync repos, auto-create webhooks for tag-based changelogs
- **Selective Repo Management:** Choose which repos to enable changelogs for — the rest stay synced but inactive
- **Notifications:** Deliver changelogs via SMTP email, SendGrid, or Slack webhooks
- **Dashboard:** Overview of repos, changelog history, and generation status with live polling (pauses when the tab is hidden)
- **Background Processing:** Changelog generation runs asynchronously — no waiting
- **Reliable Webhooks:** Signature-verified and idempotent — GitHub delivery retries never duplicate changelog generations
- **Session Hardening:** JWTs validated on app load; expired sessions redirect cleanly back to login
- **Fully Responsive:** Mobile bottom navigation, thumb-sized tap targets, and wrapping markdown so changelogs read well on any screen

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12+ / FastAPI / SQLAlchemy (async) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Frontend | React + Vite + Tailwind (source in `frontend/src/`, built output in `frontend/dist/`) |
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
   *(for a deployed server, use `http(s)://YOUR_SERVER:8003/login` — the callback must match the origin the app is served from)*
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

## Running Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

## Rebuilding the Frontend

The built app ships in `frontend/dist/`. Only rebuild if you change `frontend/src/` or `frontend/public/`:

```bash
cd frontend
npm install
npm run build   # tsc + vite build → outputs to frontend/dist/
```
## Configuration

### LLM Providers

Configured through the UI at **LLM Config** tab. Add one or more providers:

| Provider | Default Model | Requires API Key |
|----------|---------------|-----------------|
| Commit-based (free) | — | No |
| OpenAI | gpt-4o | Yes |
| Anthropic | claude-sonnet-4-20250514 | Yes |
| Groq | openai/gpt-oss-120b | Yes |
| OpenRouter | anthropic/claude-3.5-sonnet | Yes |
| Ollama | llama3.3 (localhost:11434) | No |

### Notifications

Configured through the **Notifications** tab. Options:

- **SMTP** — Any SMTP server (Gmail, Outlook, etc.)
- **SendGrid** — SendGrid email API
- **Slack** — Webhook URL + channel

### Webhooks (Auto-Generation)

When you enable a repo, the backend creates a webhook pointing to:

```
http://YOUR_SERVER_IP:8003/api/webhook
```

Changelog generation is queued automatically on:
- **Tag creation** (`create` event) — one changelog per tag
- **Release published** (`release` event)
- **Push to the default branch** — keyed by the HEAD commit SHA

Deliveries are HMAC-SHA256 signature-verified (set `GITHUB_WEBHOOK_SECRET`) and **idempotent** — if a changelog for the same tag is already pending, processing, or completed, retried deliveries are ignored instead of generating duplicates (failed ones re-queue automatically).

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
| `WEBHOOK_BASE_URL` | No | Public URL for GitHub webhook callbacks (e.g. `http://YOUR_IP:8003`) |

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
| PATCH | `/api/changelogs/configs/{id}` | Update LLM config |
| DELETE | `/api/changelogs/configs/{id}` | Delete LLM config |
| POST | `/api/changelogs/generate` | Trigger changelog generation |
| GET | `/api/changelogs/` | List changelogs |
| GET | `/api/changelogs/{id}` | Get changelog detail |
| POST | `/api/changelogs/{id}/publish-release` | Publish changelog as a GitHub Release |

### Notifications
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/notify/configs` | List notification configs |
| POST | `/api/notify/configs` | Create notification config |
| PATCH | `/api/notify/configs/{id}` | Update notification config |
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
│   ├── src/               # React source (pages, components, lib)
│   ├── public/
│   │   └── landing.html   # Cinematic landing page (copied to dist on build)
│   ├── dist/              # Built React app (served by backend)
│   │   ├── assets/
│   │   ├── index.html
│   │   └── landing.html
│   ├── index.html         # Source HTML (for rebuilding)
│   └── package.json
├── .gitignore
└── README.md
```

## License

MIT
