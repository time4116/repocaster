# repocaster

Turn a GitHub repository into a focused AI generated audio briefing.

Repocaster runs in two modes:

1. **GitHub App mode** — comment `/podcast` or `/podcast focus <topic>` on an issue or PR. Repocaster scans the repository, generates a 6 to 8 minute two host briefing, uploads the MP3 to S3, and comments back with a presigned URL.
2. **Owner only GitHub Actions mode** — manually run a workflow with repository/ref/focus inputs. This uses repo secrets and is intended for personal portfolio/demo use without requiring anyone to install the GitHub App.

## Why

Repocaster is for engineering onboarding, architecture handoffs, and focused codebase deep dives. Instead of another chatbot, it produces a portable audio explanation of how a repository works.

## Example commands

```text
/podcast
/podcast focus how LangChain and LangGraph are used
/podcast focus deployment pipeline and GitHub Actions
```

## Default constraints

- Minimum target duration: 6 minutes
- Default target duration: 6 to 8 minutes
- LLM: AWS Bedrock
- TTS: OpenAI TTS
- Output: private S3 object with presigned URL
- S3 lifecycle: generated objects expire after 10 days
- Weekly quota: S3 backed, per repo and optional global limit
- App mode: repo allowlist and author allowlist required
- Action mode: manual `workflow_dispatch`, owner guarded, no PR trigger

## High level architecture

```text
GitHub comment or manual Action
        │
        ▼
Command parser / action inputs
        │
        ▼
Repo scanner + focus aware context pack
        │
        ▼
LangGraph pipeline
  collect_context → generate_script → synthesize_audio → publish_result
        │
        ▼
S3 MP3 + GitHub comment or Actions artifact
```

## Local CLI preview

```bash
python -m repocaster.cli --repo . --mode architecture --dry-run
python -m repocaster.cli --repo . --mode focus --focus "how LangGraph is used" --dry-run
```

`--dry-run` builds the context pack and script request metadata without calling Bedrock or OpenAI.

## Bootstrap prerequisites

Before running non dry-run generation, follow the one-time setup in [`SETUP.md`](SETUP.md): create the private S3 output bucket with 10 day lifecycle expiration, create the GitHub Actions OIDC role, configure GitHub secrets/vars, and create the GitHub App for hosted bot mode.

## GitHub Actions mode

The workflow is intentionally manual and owner guarded.

```yaml
name: Repocaster

on:
  workflow_dispatch:
    inputs:
      repository:
        description: "Repository to analyze, owner/name. Defaults to this repo."
        required: false
      ref:
        description: "Branch, tag, or SHA. Defaults to current SHA."
        required: false
      focus:
        description: "Optional deep dive topic"
        required: false
      mode:
        description: "architecture or focus"
        required: false
        default: "architecture"

jobs:
  repocaster:
    if: github.actor == 'time4116'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install .
      - run: |
          repocaster \
            --repo "${{ github.workspace }}" \
            --mode "${{ inputs.mode }}" \
            --focus "${{ inputs.focus }}" \
            --output output/repocaster.mp3
        env:
          AWS_REGION: ${{ vars.AWS_REGION || 'us-east-1' }}
          BEDROCK_MODEL_ID: ${{ secrets.BEDROCK_MODEL_ID }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Repository description

```text
A GitHub App that turns repository context into focused AI generated audio briefings.
```

## Topics

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
