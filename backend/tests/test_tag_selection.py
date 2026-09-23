"""Tag *selection* (not just sorting) must be chronological and shape-agnostic.

Regression context: resolve_tags filtered with
`t.startswith("v") or t[0].isdigit()`, which admitted digit-initial SHA tags
(`0567761`) while silently dropping letter-initial ones (`f2cf1ae`) — though both
are real releases this tool created. Surviving candidates were then sorted as
*text*, so "23cf490" beat "1f21a87" and the "latest" tag could point at an older
commit, producing a changelog for the wrong range.

These tests build real repos with controlled commit dates, so the commit-time
lookups are exercised for real rather than mocked.
"""
from pathlib import Path

import pytest
from git import Actor, Repo

from app.services.git_ops import GitClient, _is_version_tag


def _commit(repo: Repo, name: str, marker: str, when: str):
    """Commit a file with a controlled author + commit date.

    `when` uses git's own date format ("YYYY-MM-DD HH:MM:SS +0000"): GitPython's
    parse_date rejects ISO-8601 strings with a 'T' and offset.
    """
    path = Path(repo.working_dir) / name
    path.write_text(marker)
    repo.index.add([name])
    actor = Actor("Tester", "tester@example.com")
    return repo.index.commit(
        f"commit {marker}", author=actor, committer=actor,
        author_date=when, commit_date=when,
    )


@pytest.fixture
def repo_with_tags(tmp_path) -> GitClient:
    """Repo where tag *text* order contradicts commit-date order."""
    repo = Repo.init(tmp_path)
    _commit(repo, "a.txt", "a", "2026-01-01 00:00:00 +0000")
    repo.create_tag("23cf490")   # lexically greatest, but the OLDEST commit
    _commit(repo, "b.txt", "b", "2026-02-01 00:00:00 +0000")
    repo.create_tag("1f21a87")   # lexically smaller, but newer
    _commit(repo, "c.txt", "c", "2026-03-01 00:00:00 +0000")
    repo.create_tag("f2cf1ae")   # letter-initial SHA: dropped by the old filter
    repo.create_tag("nightly")   # neither semver nor SHA: must stay ignored
    return GitClient(str(tmp_path))


def test_letter_initial_sha_tag_is_not_dropped(repo_with_tags):
    """f2cf1ae is the newest release; the old filter discarded it entirely."""
    from_tag, to_tag = repo_with_tags.resolve_tags()
    assert to_tag == "f2cf1ae"
    assert from_tag == "1f21a87"


def test_latest_is_chronological_not_lexical(repo_with_tags):
    """Without f2cf1ae, the newer 1f21a87 must beat the greater-text 23cf490."""
    repo_with_tags.repo.delete_tag("f2cf1ae")
    _, to_tag = repo_with_tags.resolve_tags()
    assert to_tag == "1f21a87", "text ordering would have picked 23cf490"


def test_non_version_tags_are_still_ignored(repo_with_tags):
    """With only `nightly` left there is no release anchor — fall back to HEAD."""
    repo = repo_with_tags.repo
    for tag in ("f2cf1ae", "1f21a87", "23cf490"):
        repo.delete_tag(tag)
    from_tag, to_tag = repo_with_tags.resolve_tags()
    assert to_tag == "HEAD"
    assert from_tag is None


def test_semver_resolved_by_date_not_version_number(tmp_path):
    """A later commit tagged with a *lower* semver is still the latest release."""
    repo = Repo.init(tmp_path)
    _commit(repo, "a.txt", "a", "2026-01-01 00:00:00 +0000")
    repo.create_tag("v0.9.0")
    _commit(repo, "b.txt", "b", "2026-02-01 00:00:00 +0000")
    repo.create_tag("v1.10.0")
    _commit(repo, "c.txt", "c", "2026-03-01 00:00:00 +0000")
    repo.create_tag("v1.2.0")

    from_tag, to_tag = GitClient(str(tmp_path)).resolve_tags()
    assert to_tag == "v1.2.0"
    assert from_tag == "v1.10.0"


def test_semver_preferred_over_sha_on_same_commit(tmp_path):
    """Two tags on one commit: the readable version wins as latest."""
    repo = Repo.init(tmp_path)
    _commit(repo, "a.txt", "a", "2026-01-01 00:00:00 +0000")
    repo.create_tag("0567761")   # what our publisher creates
    repo.create_tag("v1.0.0")    # what a human created for the same commit

    _, to_tag = GitClient(str(tmp_path)).resolve_tags()
    assert to_tag == "v1.0.0", "a readable version beats a bare hash on a tie"


def test_explicit_tags_short_circuit(repo_with_tags):
    assert repo_with_tags.resolve_tags("v1.0.0", "v2.0.0") == ("v1.0.0", "v2.0.0")


def test_tag_shape_classifier():
    for good in ("v1.2.3", "1.2", "v0.1", "0567761", "f2cf1ae", "abc1234"):
        assert _is_version_tag(good), good
    for bad in ("", "nightly", "docs-fix", "release-1", "1234zz", "v"):
        assert not _is_version_tag(bad), bad
