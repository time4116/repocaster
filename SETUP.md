# End-to-End Setup

## Before you start

You need:

- AWS account with permission to create S3 buckets, IAM roles, OIDC providers, and later CDK resources
- AWS CLI configured locally
- Python 3.11+
- GitHub repository `time4116/repocaster`
- Bedrock model access enabled in your AWS account
- OpenAI API key for TTS
- `ffmpeg` for local non dry-run generation

---

## 1. Create the GitHub repository

Create the repository manually if the current token cannot create repos or push workflow files:

```text
Name: repocaster
Visibility: public
Description: A GitHub App that turns repository context into focused AI generated audio briefings.
```

Recommended topics:

```text
github-app
aws-bedrock
langgraph
langchain
openai-tts
devops-automation
repo-analysis
podcast
llm
```

Push this local repo after creating it:

```bash
cd /opt/data/repocaster
git remote add origin https://github.com/time4116/repocaster.git
git push -u origin main
```

---

## 2. Enable Bedrock model access

In the AWS Console:

```text
Amazon Bedrock → Model access
```

Enable the Claude model you want to use, then set the model ID as the GitHub secret:

```text
BEDROCK_MODEL_ID
```

Example placeholder:

```text
anthropic.claude-3-5-haiku-20241022-v1:0
```

---

## 3. Create the private S3 output bucket

Generated MP3s and metadata should live in a private bucket with a 10 day lifecycle policy.

```bash
cd /opt/data/repocaster
python scripts/create_output_bucket.py \
  --bucket repocaster-output-<unique-suffix> \
  --region us-east-1 \
  --retention-days 10
```

The script configures:

- public access block
- AES256 server-side encryption
- lifecycle expiration after 10 days
- incomplete multipart upload cleanup after 1 day

---

## 4. Create the GitHub Actions OIDC role

Actions mode is for André only. It uses GitHub OIDC rather than long-lived AWS keys.

```bash
python scripts/create_actions_role.py \
  --owner time4116 \
  --repo repocaster \
  --role-name repocaster-actions \
  --bucket repocaster-output-<unique-suffix> \
  --region us-east-1 \
  --bedrock-model-id <same BEDROCK_MODEL_ID used by bedrock-pr-agent>
```

The script prints the role ARN. Save it as the GitHub Actions secret:

```text
AWS_ROLE_ARN
```

The role allows only the configured Bedrock model resource plus the Repocaster S3 bucket. If you pass a model ID such as `anthropic.claude-3-5-haiku-20241022-v1:0`, the script scopes Bedrock permissions to:

```text
arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0
```

If `bedrock-pr-agent` uses an inference profile ARN, pass that full ARN instead.

The role allows:

- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- S3 object access only to the Repocaster output bucket

---

## 5. Configure GitHub Actions secrets and variables

Repository secrets:

```text
AWS_ROLE_ARN=<role ARN from step 4>
BEDROCK_MODEL_ID=<Bedrock model ID>
OPENAI_API_KEY=<OpenAI API key>
```

Repository variables:

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

---

## 6. Run Actions mode

The owner-only workflow is:

```text
.github/workflows/repocaster.yml
```

It is intentionally restricted:

- manual `workflow_dispatch` only
- job-level guard: `github.actor == 'time4116'`
- defaults to `dry_run: true`
- no PR trigger
- configures AWS credentials only for real runs
- installs ffmpeg for real runs

For a real run, trigger the workflow manually and set:

```text
dry_run=false
mode=architecture
```

or:

```text
dry_run=false
mode=focus
focus=how LangGraph is used
```

Output is uploaded as an Actions artifact. If `OUTPUT_BUCKET` is set, Repocaster also uploads the MP3 and metadata to S3 and emits a presigned URL.

---

## 7. Create the GitHub App for hosted bot mode

Actions mode works without the bot. Hosted App mode needs a GitHub App and deployed webhook infrastructure.

Generate a starter manifest:

```bash
python scripts/github_app_manifest.py
```

Minimum GitHub App permissions:

- Metadata: read
- Contents: read
- Issues: read/write
- Pull requests: read

Webhook events:

```text
issue_comment
```

The bot command UX is:

```text
/podcast
/podcast focus <topic>
```

Store the GitHub App credentials in AWS Secrets Manager. Shape:

```json
{
  "app_id": "123456",
  "webhook_secret": "<webhook secret>",
  "private_key": "<GitHub App private key PEM>"
}
```

Never commit the webhook secret or private key.

---

## 8. Deploy hosted App infrastructure

Planned hosted mode infrastructure:

- API Gateway HTTP API
- webhook Lambda
- SQS queue + DLQ
- worker Lambda
- private S3 output/quota bucket
- Secrets Manager GitHub App credentials
- Bedrock invoke permissions
- OpenAI API key secret

This is intentionally separate from owner-only Actions mode. Actions mode is the first working path; hosted App mode follows the same skeleton as `bedrock-pr-agent`.

---

## 9. Validate before pushing public changes

Run:

```bash
ruff check .
pytest -q
python -m compileall -q src tests scripts
bandit -q -r src scripts -x tests
pip-audit
```

Security checks include:

- public repo safety tests
- secret scanning patterns
- workflow trigger/permission checks
- owner-only Action guard checks
- allowed secret reference checks

---

## Detailed reference

Additional bootstrap notes live in:

```text
docs/BOOTSTRAP.md
```
