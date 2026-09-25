"""Push vs release range bases.

Regression guard for: every push re-covering everything since the last tag,
so yesterday's changes kept reappearing in today's changelog (commit count
creeping up by one each push).
"""
from git import Actor
from git import Repo as GitRepo

from app.services.changelog_service import resolve_range_base
from app.services.git_ops import GitClient



def _make_repo(path, commits=5):
    repo = GitRepo.init(path)
    actor = Actor("Tester", "tester@example.com")
    shas = []
    for i in range(commits):
        f = path / f"f{i}.txt"
        f.write_text(f"{i}\n")
        repo.index.add([f.name])
        c = repo.index.commit(f"commit {i}", author=actor, committer=actor)
        shas.append(c.hexsha)
    return repo, shas


def test_push_prefers_last_generated_commit(tmp_path):
    repo, shas = _make_repo(tmp_path)
    repo.create_tag("v1.0.0", ref=shas[1])   # released long ago
    git = GitClient(str(tmp_path))

    base, incremental = resolve_range_base(git, "v1.0.0", shas[4], shas[3])
    assert base == shas[3]          # not the stale tag
    assert incremental is True


def test_second_push_covers_only_new_commit(tmp_path):
    """The exact reported symptom: pushes must not re-cover the backlog."""
    repo, shas = _make_repo(tmp_path, 6)
    repo.create_tag("v1.0.0", ref=shas[0])
    git = GitClient(str(tmp_path))

    # First generation ever: no tracking yet → tag base stands.
    base1, inc1 = resolve_range_base(git, "v1.0.0", shas[2], None)
    assert (base1, inc1) == ("v1.0.0", False)

    # Tracking advanced to shas[3]; the next push is shas[4].
    base2, inc2 = resolve_range_base(git, "v1.0.0", shas[4], shas[3])
    assert base2 == shas[3] and inc2 is True
    assert len(list(repo.iter_commits(f"{base2}..{shas[4]}"))) == 1


def test_older_tracking_does_not_move_the_base_backwards(tmp_path):
    repo, shas = _make_repo(tmp_path)
    repo.create_tag("v1.0.0", ref=shas[2])
    git = GitClient(str(tmp_path))

    base, incremental = resolve_range_base(git, "v1.0.0", shas[4], shas[0])
    assert base == "v1.0.0" and incremental is False


def test_rewritten_history_keeps_the_tag_base(tmp_path):
    """last_generated_commit that isn't an ancestor must not be used."""
    repo, shas = _make_repo(tmp_path)
    repo.create_tag("v1.0.0", ref=shas[0])
    git = GitClient(str(tmp_path))

    base, incremental = resolve_range_base(git, "v1.0.0", shas[2], shas[4])
    assert base == "v1.0.0" and incremental is False


def test_missing_inputs_are_left_alone(tmp_path):
    repo, shas = _make_repo(tmp_path, 3)
    git = GitClient(str(tmp_path))

    assert resolve_range_base(git, None, shas[2], shas[1]) == (None, False)
    assert resolve_range_base(git, shas[0], None, shas[1]) == (shas[0], False)
    assert resolve_range_base(git, shas[0], shas[2], None) == (shas[0], False)


def test_has_tag_separates_releases_from_shas(tmp_path):
    repo, shas = _make_repo(tmp_path, 2)
    repo.create_tag("v1.0.0")
    git = GitClient(str(tmp_path))

    assert git.has_tag("v1.0.0") is True
    assert git.has_tag(shas[1]) is False    # a bare commit SHA is a push target
    assert git.has_tag("HEAD") is False
    assert git.has_tag("") is False


def test_unchanged_repo_keeps_the_tag_base(tmp_path):
    """Nothing new (tracking == target) must not produce an empty range.

    An empty incremental range would replace the previous, meaningful
    changelog for the same tag with a "no commits" one.
    """
    repo, shas = _make_repo(tmp_path, 4)
    repo.create_tag("v1.0.0", ref=shas[1])
    git = GitClient(str(tmp_path))

    base, incremental = resolve_range_base(git, "v1.0.0", shas[3], shas[3])
    assert base == "v1.0.0" and incremental is False
