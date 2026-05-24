# Security

Repocaster is designed for low cost personal use and public repo safety.

## Supported security controls

- GitHub webhook HMAC verification
- fail closed repository allowlist
- author allowlist for `/podcast` commands
- no automatic execution on untrusted pull requests
- private S3 objects delivered through presigned URLs
- S3 lifecycle expiration for generated media after 10 days
- weekly execution quotas stored in S3
- context pack file ignore rules for secrets, generated output, media, dependencies, and build artifacts

## Secret handling

Do not commit:

- `.env` files
- GitHub App private keys
- OpenAI keys
- AWS credentials
- generated audio

GitHub App credentials should live in AWS Secrets Manager. GitHub Actions mode should use repository secrets and manual `workflow_dispatch` only.

## Public usage warning

The included GitHub Actions mode is intended for owner only use. Do not add `pull_request` triggers to secret bearing podcast workflows.
