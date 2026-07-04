import base64
import hashlib
import hmac
import json

from repocaster.config import Settings
from repocaster.github_app.webhook import handle_issue_comment, lambda_handler, verify_signature


def _signature(payload: str, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_hmac():
    payload = '{"ok": true}'
    secret = "webhook-secret"
    assert verify_signature(payload, _signature(payload, secret), secret)


def test_lambda_handler_fails_closed_without_webhook_secret(monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    response = lambda_handler(
        {
            "body": '{"ok": true}',
            "headers": {
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": "sha256=ignored",
            },
        },
        None,
    )
    assert response["statusCode"] == 500
    assert json.loads(response["body"])["error"] == "webhook secret not configured"


def test_lambda_handler_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    response = lambda_handler(
        {
            "body": '{"ok": true}',
            "headers": {
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": "sha256=bad",
            },
        },
        None,
    )
    assert response["statusCode"] == 401


def test_lambda_handler_rejects_missing_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    response = lambda_handler(
        {"body": '{"ok": true}', "headers": {"X-GitHub-Event": "issue_comment"}},
        None,
    )
    assert response["statusCode"] == 401


def test_lambda_handler_accepts_lowercase_github_headers(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    body = json.dumps(
        {
            "repository": {"full_name": "time4116/repocaster"},
            "comment": {"body": "/podcast", "user": {"login": "time4116"}},
        }
    )
    response = lambda_handler(
        {
            "body": body,
            "headers": {
                "x-github-event": "issue_comment",
                "x-hub-signature-256": _signature(body, "webhook-secret"),
            },
        },
        None,
    )
    assert response["statusCode"] == 202


def test_lambda_handler_decodes_base64_event_body_before_verifying_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    monkeypatch.setenv("ALLOWED_REPOS", "time4116/repocaster")
    monkeypatch.setenv("ALLOWED_USERS", "time4116")
    body = json.dumps(
        {
            "repository": {"full_name": "time4116/repocaster"},
            "comment": {"body": "/podcast", "user": {"login": "time4116"}},
        }
    )
    response = lambda_handler(
        {
            "body": base64.b64encode(body.encode()).decode(),
            "isBase64Encoded": True,
            "headers": {
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": _signature(body, "webhook-secret"),
            },
        },
        None,
    )
    assert response["statusCode"] == 202
    payload = json.loads(response["body"])
    assert payload["message"] == "accepted"


def test_lambda_handler_rejects_invalid_base64_event_body(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "webhook-secret")
    response = lambda_handler(
        {
            "body": "not-valid-base64",
            "isBase64Encoded": True,
            "headers": {
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": "sha256=ignored",
            },
        },
        None,
    )
    assert response["statusCode"] == 400


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


def test_handle_issue_comment_marks_pr_comments_for_pr_focused_generation():
    payload = {
        "repository": {"full_name": "time4116/repocaster"},
        "issue": {"number": 17, "pull_request": {"url": "https://api.github.com/pr/17"}},
        "comment": {"body": "/podcast", "user": {"login": "time4116"}},
    }
    settings = Settings(allowed_repos=("time4116/repocaster",), allowed_users=("time4116",))
    result = handle_issue_comment(payload, settings)
    assert result is not None
    assert result["accepted"] is True
    assert result["pull_request"] == "17"


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
