from repocaster.config import Settings
from repocaster.github_app.webhook import handle_issue_comment, verify_signature


def test_verify_signature_accepts_valid_hmac():
    import hashlib
    import hmac

    payload = '{"ok": true}'
    secret = "webhook-secret"
    signature = "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    assert verify_signature(payload, signature, secret)


def test_handle_issue_comment_accepts_allowed_command():
    payload = {
        "repository": {"full_name": "time4116/repocaster"},
        "comment": {"body": "/podcast focus langchain", "user": {"login": "time4116"}},
    }
    settings = Settings(allowed_repos=("time4116/repocaster",), allowed_users=("time4116",))
    result = handle_issue_comment(payload, settings)
    assert result is not None
    assert result["accepted"] is True
    assert result["command"]["mode"] == "focus"


def test_handle_issue_comment_rejects_unallowed_user():
    payload = {
        "repository": {"full_name": "time4116/repocaster"},
        "comment": {"body": "/podcast", "user": {"login": "someone"}},
    }
    settings = Settings(allowed_repos=("time4116/repocaster",), allowed_users=("time4116",))
    result = handle_issue_comment(payload, settings)
    assert result is not None
    assert result["accepted"] is False
    assert result["reason"] == "user not allowed"
