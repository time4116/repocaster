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
- context pack file ignore rules for credential stores (`.aws`, `.ssh`, `.kube`, `.docker`, `.config/gh`, `.config/gcloud`, and similar directories), authentication dotfiles including `.git-credentials`, private keys, Terraform state, plan outputs (`*.tfplan`, `*.tfplan.*`, `terraform.plan`) and variable values, generated output, media, dependencies, and build artifacts. The same path filtering applies to pull request diff excerpts, including deleted files, and synthetic context files. Example templates such as `.env.example` and `*.tfvars.example` remain eligible. Terraform can write plans to arbitrary filenames with `-out`; avoid committing or submitting those files.

Path filtering cannot detect secrets pasted into otherwise ordinary source files, documentation, or pull request descriptions. Review repositories and diffs before sending context to Bedrock.

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
