# Project Brief — auto-changelog

## Mission
Automatically generate beautiful, AI-powered changelogs for GitHub repositories, with multiple LLM providers and notification channels.

## Core features (implemented)
- GitHub OAuth login + JWT sessions
- Repo sync + selective activation; auto-created webhooks for tag-based changelogs
- Changelog generation: OpenAI, Anthropic, Groq, OpenRouter, Ollama (local), or free commit-based mode
- Incremental changelogs with real version headings
- Notifications: SMTP email, SendGrid, Slack webhooks
- Background/async generation pipeline (no blocking waits)
- Dashboard serving pre-built frontend from `frontend/dist/`

## Architecture
- `backend/app/main.py` — FastAPI app
- `backend/app/api/` — routers (auth, repos, changelogs, webhooks)
- `backend/app/services/` — LLM providers, GitHub client, changelog generation, notifications
- `backend/app/tasks/` — background processing
- `backend/app/models/` + `app/schemas/` — SQLAlchemy models / Pydantic DTOs
- `backend/alembic/` — migrations
- SQLite in dev (`backend/data/`), PostgreSQL in prod

## Constraints
- Single-user/small-team deployment; secrets stay out of git
- Frontend source not in repo — dist is shipped pre-built
