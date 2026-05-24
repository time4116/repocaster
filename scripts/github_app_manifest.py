#!/usr/bin/env python3
from __future__ import annotations

import json

MANIFEST = {
    "name": "Repocaster",
    "url": "https://github.com/time4116/repocaster",
    "hook_attributes": {"url": "https://example.com/github/webhook"},
    "redirect_url": "http://127.0.0.1:8765/callback",
    "public": False,
    "default_permissions": {
        "metadata": "read",
        "contents": "read",
        "issues": "write",
        "pull_requests": "read",
    },
    "default_events": ["issue_comment"],
}


if __name__ == "__main__":
    print(json.dumps(MANIFEST, indent=2))
