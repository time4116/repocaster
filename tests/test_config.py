from repocaster.config import Settings, repo_allowed, user_allowed


def test_repo_allowlist_fails_closed():
    settings = Settings(allowed_repos=(), allowed_users=("time4116",))
    assert not repo_allowed("time4116/repocaster", settings)


def test_repo_allowlist_accepts_explicit_repo():
    settings = Settings(allowed_repos=("time4116/repocaster",), allowed_users=("time4116",))
    assert repo_allowed("time4116/repocaster", settings)
    assert not repo_allowed("someone/else", settings)


def test_user_allowlist_fails_closed():
    settings = Settings(allowed_repos=("time4116/repocaster",), allowed_users=())
    assert not user_allowed("time4116", settings)
