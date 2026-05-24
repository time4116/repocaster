# Repocaster bootstrap prerequisites

Repocaster has two execution modes. Both need a one-time bootstrap before real non dry-run generation.

## 1. Create the GitHub repository

Create `time4116/repocaster` manually or with a token that has repo creation and workflow permissions.

Recommended settings:

- Public repository
- Default branch: `main`
- Only André has write/admin access
- Enable branch protection before accepting outside PRs

## 2. GitHub Actions mode prerequisites

Actions mode is for André only. It is manual and owner gated.

### AWS resources

Create the private output bucket with 10 day lifecycle expiration:

```bash
python scripts/create_output_bucket.py \
  --bucket repocaster-output-<unique-suffix> \
  --region us-east-1 \
  --retention-days 10
```

Create or update the GitHub Actions OIDC role:

```bash
python scripts/create_actions_role.py \
  --owner time4116 \
  --repo repocaster \
  --role-name repocaster-actions \
  --bucket repocaster-output-<unique-suffix> \
  --region us-east-1 \
  --bedrock-model-id <same BEDROCK_MODEL_ID used by bedrock-pr-agent>
```

The role allows only the configured Bedrock model resource plus the Repocaster S3 bucket:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- object access to the Repocaster S3 bucket

The role trust policy is scoped to `time4116/repocaster` on `main` and GitHub environments.

### GitHub repository secrets

Set these repository secrets:

```text
AWS_ROLE_ARN=<role ARN from create_actions_role.py>
BEDROCK_MODEL_ID=<chosen Bedrock model id>
OPENAI_API_KEY=<OpenAI API key>
```

### GitHub repository variables

Set these repository variables:

```text
AWS_REGION=us-east-1
OUTPUT_BUCKET=repocaster-output-<unique-suffix>
```

Optional variables:

```text
OPENAI_TTS_MODEL=tts-1-hd
OPENAI_TTS_VOICE_A=nova
OPENAI_TTS_VOICE_B=shimmer
MIN_EPISODE_MINUTES=6
MAX_EPISODE_MINUTES=8
S3_RETENTION_DAYS=10
```

### GitHub Action behavior

`.github/workflows/repocaster.yml`:

- only runs via `workflow_dispatch`
- requires `github.actor == 'time4116'`
- defaults to `dry_run: true`
- installs ffmpeg before real generation
- configures AWS credentials only when `dry_run != 'true'`
- uploads generated output as an Actions artifact

## 3. GitHub App mode prerequisites

This is the public portfolio/demo path, similar to `bedrock-pr-agent`.

Required setup:

1. Create a GitHub App named `Repocaster`.
2. Store app credentials in AWS Secrets Manager.
3. Deploy webhook/API/SQS/worker/CDK infrastructure.
4. Configure allowed repos/users and weekly quotas.

Minimum GitHub App permissions:

- Repository contents: read
- Metadata: read
- Issues: read/write, for top-level PR/issue comments
- Pull requests: read, if supporting PR comments

Webhook events:

- `issue_comment`

Secrets Manager shape:

```json
{
  "app_id": "123456",
  "webhook_secret": "...",
  "private_key": "<GitHub App private key PEM>"
}
```

Never commit the private key or webhook secret.

## 4. Cost and storage controls

Required controls:

- `ALLOWED_USERS=time4116`
- `ALLOWED_REPOS=time4116/repocaster,time4116/bedrock-pr-agent`
- weekly execution quota stored in S3
- cache by repo/ref/mode/focus/prompt version
- generated S3 objects expire after 10 days
- presigned URLs only, no public bucket policy

## 5. Local validation before push

Run:

```bash
ruff check .
pytest -q
python -m compileall -q src tests scripts
bandit -q -r src scripts -x tests
pip-audit
```

The public repo safety tests must pass before pushing.
