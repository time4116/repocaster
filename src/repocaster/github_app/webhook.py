from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from repocaster.commands import parse_podcast_command
from repocaster.config import Settings, repo_allowed, user_allowed


def verify_signature(payload: str, signature: str, secret: str) -> bool:
    if not signature.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def event_body(event: dict[str, Any]) -> str:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        return base64.b64decode(body).decode("utf-8")
    return body


def handle_issue_comment(payload: dict[str, Any], settings: Settings) -> dict[str, Any] | None:
    repo = payload.get("repository", {}).get("full_name", "")
    user = payload.get("comment", {}).get("user", {}).get("login", "")
    body = payload.get("comment", {}).get("body", "")
    command = parse_podcast_command(body)
    if command is None:
        return None
    if not repo_allowed(repo, settings):
        return {"accepted": False, "reason": "repo not allowed", "repo": repo}
    if not user_allowed(user, settings):
        return {"accepted": False, "reason": "user not allowed", "user": user}
    result: dict[str, Any] = {
        "accepted": True,
        "repo": repo,
        "user": user,
        "command": command.__dict__,
    }
    issue = payload.get("issue", {})
    if issue.get("pull_request") and issue.get("number"):
        result["pull_request"] = str(issue["number"])
    return result


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    try:
        body = event_body(event)
    except (ValueError, UnicodeDecodeError):
        return {"statusCode": 400, "body": json.dumps({"error": "invalid request body"})}
    headers = event.get("headers") or {}
    event_name = headers.get("x-github-event") or headers.get("X-GitHub-Event")
    signature = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256") or ""
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "webhook secret not configured"}),
        }
    if not verify_signature(body, signature, webhook_secret):
        return {"statusCode": 401, "body": json.dumps({"error": "invalid signature"})}
    if event_name != "issue_comment":
        return {"statusCode": 202, "body": json.dumps({"message": "ignored event"})}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": json.dumps({"error": "invalid request body"})}

    result = handle_issue_comment(payload, Settings.from_env())
    if result and result.get("accepted"):
        # TODO: enqueue to SQS after CDK stack is added.
        return {"statusCode": 202, "body": json.dumps({"message": "accepted", "job": result})}
    return {"statusCode": 202, "body": json.dumps({"message": "ignored", "result": result})}
