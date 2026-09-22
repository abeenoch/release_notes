"""Tag resolution must never crash on non-semver tags (e.g. SHA-style tags).

Regression: release_notes is tagged with commit SHAs; the old sort key produced
[int] for '0567761' and [str] for '1f21a87', and comparing them raised
`TypeError: '<' not supported between instances of 'str' and 'int'` — failing
every push-generated changelog for such repos.
"""
from app.services.git_ops import _semver_sort_key


def test_sort_key_never_mixes_int_and_str():
    tags = ["0567761", "1f21a87", "3b8565a", "c8448a6", "f2cf1ae"]
    ordered = sorted(tags, key=_semver_sort_key)  # raised before the fix
    assert sorted(ordered) == sorted(tags)  # nothing lost, deterministic


def test_sort_key_still_orders_semver():
    assert sorted(["v1.2.0", "v1.10.0", "v1.2.1", "v0.9.0"], key=_semver_sort_key) == [
        "v0.9.0", "v1.2.0", "v1.2.1", "v1.10.0",
    ]
