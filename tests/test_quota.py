import pytest

from repocaster.quota import dump_quota, load_quota, quota_key, record_execution


def test_quota_key_is_repo_safe():
    assert (
        quota_key("time4116/repocaster", "2026-W21")
        == "quotas/week/2026-W21/time4116__repocaster.json"
    )


def test_record_execution_enforces_limit():
    quota = load_quota(None, "time4116/repocaster", limit=1, week="2026-W21")
    record_execution(quota, {"user": "time4116"})
    with pytest.raises(ValueError):
        record_execution(quota, {"user": "time4116"})


def test_quota_roundtrip():
    quota = load_quota(None, "time4116/repocaster", limit=2, week="2026-W21")
    record_execution(quota, {"commit": "abc123"})
    loaded = load_quota(dump_quota(quota), "time4116/repocaster", limit=2, week="2026-W21")
    assert loaded.count == 1
    assert loaded.executions[0]["commit"] == "abc123"
