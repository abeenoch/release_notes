# Changelog — c8448a6

_Updates since 4ad29d955471e013c63c04d293ff959658273718, through c8448a6_

# Changelog — c8448a6

## Summary
Corrected timestamp handling across API response schemas so that UTC times are emitted with proper timezone information, preventing a one‑hour offset in client displays.

## Features
*None*

## Bug Fixes
- Fixed timestamps that appeared ~1 hour off by attaching UTC tzinfo to naive `created_at` fields in changelog, LLM config, notify config, and repository response schemas. The API now returns ISO‑8601 strings with a “Z” suffix.

## Other Changes
- Added a shared `_ensure_utc` helper and `field_validator` hooks to the affected Pydantic models.

## Full Commit Log
```
c8448a6 2026-09-09 12:09:35 — fix: timestamps showed ~1h off (naive UTC misread as local)

SQLite stores created_at as UTC but returns naive datetimes (no
tzinfo), so the API serialized them without an offset (e.g.
'2026-09-09T09:53:31'). Browsers' new Date() then interpreted those
as local time — a UTC+1 user saw a just-created item as '1 hour ago'.

Attach UTC tzinfo via a field_validator(mode='before') on created_at
in every response schema (changelog, llm config, notify config, repo).
The API now emits '...Z' offsets and browsers convert to local time
correctly.
```
