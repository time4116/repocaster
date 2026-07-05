# Repocaster Architecture

## Operating modes

Repocaster has one shared core pipeline and two entrypoints.

```text
GitHub App webhook     GitHub Actions workflow
        │                        │
        └──────────┬─────────────┘
                   ▼
            shared core pipeline
                   ▼
        S3 output + GitHub response
```

## GitHub App mode (target design, partially built)

```text
Issue/PR comment: /podcast [focus <topic>]
        │
        ▼
API Gateway HTTP API
        │
        ▼
Webhook Lambda
  - verify GitHub HMAC
  - parse command
  - enforce ALLOWED_REPOS
  - enforce ALLOWED_USERS
  - check S3 weekly quota
        │
        ▼
SQS
        │
        ▼
Worker Lambda
  - fetch installation token
  - scan repository
  - build context pack
  - run the generation pipeline
  - upload MP3 to S3
  - post GitHub comment
```

Status: the webhook Lambda (HMAC verification, command parsing, repo and author
allowlists) is implemented in `src/repocaster/github_app/webhook.py`. The quota
check, SQS queue, and worker Lambda are not built yet; accepted commands are
acknowledged and dropped.

## Manual workflow mode

Manual workflow mode is for the repository owner only. It runs from the Repocaster repo, uses repository secrets, accepts optional target repository/ref inputs, and does not run on pull requests.

```text
workflow_dispatch
        │
        ▼
owner guard: github.actor == time4116
        │
        ▼
checkout Repocaster and target repo
        │
        ▼
repocaster CLI
        │
        ▼
MP3 artifact or optional S3 upload
```

## Shared pipeline

```text
scan_repo
  → build_context_pack
  → generate_structured_script
  → validate_duration_and_segments
  → synthesize_audio_segments
  → stitch_audio
  → publish_result
```

## Focus mode

Focus mode accepts free text, for example:

```text
/podcast focus how LangChain is used
```

Context selection is biased toward:

- file paths containing focus tokens
- files importing related packages
- docs mentioning the focus phrase
- nearby manifests, deployment files, and entrypoints

The generated briefing should remain grounded in repository context and avoid unrelated whole repo summary except where necessary.

## Cost controls

- author allowlist
- repo allowlist
- command only trigger
- S3 backed weekly quota
- cache by repo/ref/mode/focus/prompt version
- context size caps
- S3 lifecycle expiration after 10 days
- presigned URLs instead of public buckets
