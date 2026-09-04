# Active Context

> Cline: read this at task start. Update it at task end (last 3 sections).

## Current focus
- Incremental changelog generation + version headings recently landed (commit 690c7da)
- GitHub App webhook config for push-to-default-branch support

## Known issues / TODO
- arq task queue commented out in requirements.txt — currently in-process background work; Redis-based queue pending
- Frontend source not in repo; any frontend change requires finding source or rebuilding externally

## Decisions log
- Commit-based mode kept as free fallback (no API key required)
- SQLite in dev, PostgreSQL in prod (asyncpg)
