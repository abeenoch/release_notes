# Release Notes

Automatically generate beautiful, AI-powered changelogs for your GitHub repositories. Supports multiple LLM providers and notification channels.

## Features

- **Cinematic landing page + dark-branded login:** OAuth flow returns straight into the app (`/login`) — no page flashes, CSRF-protected with OAuth `state`
- **Multiple LLM Providers:** OpenAI, Anthropic, Groq, OpenRouter, Ollama (local), or commit-based mode (free, no API key)
- **GitHub Integration:** OAuth login, sync repos, auto-create webhooks for tag-based changelogs
- **Selective Repo Management:** Choose which repos to enable changelogs for — the rest stay synced but inactive
- **Public Changelog Pages:** Opt-in vanity URLs at `/owner/repo` — share one link, no login required
- **Email Subscribers:** Double opt-in subscribe box on public pages; releases are sent through **your own** SMTP/SendGrid config (no platform-wide sender)
- **Embeddable Widget:** Drop a single `<script>` tag on any site/portfolio to render a repo's latest releases
- **Manual Range Trigger:** Generate a changelog for an explicit `From → To` ref range (validated before queueing)
- **Notifications:** Deliver changelogs via SMTP email, SendGrid, or Slack webhooks
- **Dashboard:** Overview of repos, changelog history, and generation status with live polling (pauses when the tab is hidden)
- **Background Processing:** Changelog generation runs asynchronously — no waiting
- **Reliable Webhooks:** Signature-verified and idempotent — GitHub delivery retries never duplicate changelog generations; repos resolve by GitHub's numeric ID and fan out to *every* user who registered them
- **Session Hardening:** JWTs validated on app load; expired sessions redirect cleanly back to login
- **Fully Responsive:** Mobile bottom navigation, thumb-sized tap targets, and wrapping markdown so changelogs read well on any screen
- **CI:** GitHub Actions runs backend tests + frontend typecheck/build on every push and PR

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
4. Click a repo name → **"Generate Now"** for the default incremental range, or **"Range…"** and enter explicit `From` / `To` refs (e.g. `v1.0.0` → `v1.1.0`)

## Public Changelog Pages & Embeddable Widget

Share a repo's release notes with anyone — no account needed.

### Vanity URL (`/owner/repo`)

1. Open a repo's detail page (**Repositories → click a repo**).
2. In the **"Public changelog page"** card, click **Enable**.
3. Share the shown link, e.g. `https://YOUR-SERVER/owner/repo`.

Details:

- **Opt-in, default OFF** — registering a repo never publishes it; Disable hides the page again (it returns 404, not 403, so unpublished pages don't leak their existence).
- Only **completed** changelogs are served, through a dedicated schema: no IDs, statuses, error messages, or notification state ever leave the server.
- Works for private repos too — the page is explicit opt-in — but everything on an enabled page is world-readable.

### Email subscribers

When a public page is enabled, it shows a **"Get release notes by email"** box:

- **Double opt-in:** subscribing sends a confirmation email; nothing is mailed until the link is clicked. Separate tokens protect confirm vs. unsubscribe links.
- **Sends via your own config:** confirmation and release emails go through your active **SMTP/SendGrid** config (Notifications tab) — there is no platform-wide sender. If no email-capable config exists, subscribing returns a clear 400 and fan-out is recorded as `skipped` (Slack-only configs can't address email).
- Links in those emails use `PUBLIC_BASE_URL`, falling back to `WEBHOOK_BASE_URL`.

### Embeddable widget

Paste onto any site (portfolio, blog, docs) — one tag per repo:

```html
<script src="https://YOUR-SERVER/widget.js" data-repo="owner/repo" async></script>
```

- Renders the repo's latest releases (default 5 — override with `data-limit="10"`, max 50) inside a **shadow DOM**, so your site's CSS and the widget's styles can't interfere with each other.
- **Read-only:** it fetches the public endpoint (open CORS on `/api/public/*` only) and links to your vanity page for "View all & subscribe".
- Requires the repo's public page to be enabled; otherwise it shows "Changelog unavailable".
- The repo detail page shows the ready-made snippet with a **Copy** button next to the public-page card.

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
| `PUBLIC_BASE_URL` | No | Origin for confirm/unsubscribe links in subscriber emails (falls back to `WEBHOOK_BASE_URL`) |

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
| PATCH | `/api/repos/{id}/public` | Enable/disable the public vanity page |
| DELETE | `/api/repos/{id}` | Remove a repo |

### Changelogs
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/changelogs/configs` | List LLM configs |
| POST | `/api/changelogs/configs` | Create LLM config |
| PATCH | `/api/changelogs/configs/{id}` | Update LLM config |
| DELETE | `/api/changelogs/configs/{id}` | Delete LLM config |
| POST | `/api/changelogs/generate` | Trigger generation (optional `from_tag`/`to_tag` — both or neither) |
| GET | `/api/changelogs/` | List changelogs (paginated; includes `total`) |
| GET | `/api/changelogs/stats/summary` | Full totals for dashboards (ignores pagination) |
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

### Public (unauthenticated, open CORS)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/public/{owner}/{repo}` | Public changelog page data (opt-in repos, completed only) |
| POST | `/api/public/{owner}/{repo}/subscribe` | Start double opt-in subscription |
| GET | `/api/public/confirm/{token}` | Confirm a subscription |
| GET | `/api/public/unsubscribe/{token}` | Unsubscribe |
| GET | `/widget.js` | Embeddable widget script |

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
│   │   ├── landing.html   # Cinematic landing page (copied to dist on build)
│   │   └── widget.js      # Embeddable changelog widget (copied to dist on build)
│   ├── dist/              # Built React app (served by backend)
│   │   ├── assets/
│   │   ├── index.html
│   │   ├── landing.html
│   │   └── widget.js
│   ├── index.html         # Source HTML (for rebuilding)
│   └── package.json
├── .github/workflows/     # CI: backend pytest + frontend build on push/PR
├── .gitignore
└── README.md
```

## License

MIT
