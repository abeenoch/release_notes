# Changelog Release Workflow

Reusable task: generate changelog for the latest tag / release.

## Steps

1. **Determine scope**: `git fetch --tags` and identify the latest tag and the commits since the previous tag (`git log --oneline <prev-tag>..<latest-tag>`). If no tags exist, use commits since the last release commit.

2. **Categorize commits** by conventional-commit prefix:
   - `feat:` → Added
   - `fix:` → Fixed
   - `perf:` → Performance
   - `refactor:` → Changed
   - `docs:` → Documentation
   - `chore:`/`build:`/`ci:` → Internal (usually omit unless notable)

3. **Draft the changelog** in Keep a Changelog format, human-readable (not commit dumps), linking PRs/commits where useful. Follow the style of the project's own generated changelogs.

4. **Update CHANGELOG.md** at repo root: insert the new `## [version] - <date>` section under the `## [Unreleased]` header (create the file with `# Changelog` header if missing).

5. **Validate**: confirm the markdown renders sensibly (no duplicated headings, correct version/date), and run `git diff` to show me the result.

6. **Do NOT commit or tag automatically** — present the diff and wait for my approval, unless I explicitly said "commit it" in the task prompt.
