# Repocaster MVP Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Build a low-cost GitHub App and owner-only GitHub Actions workflow that generates 6 to 8 minute audio briefings from repository context.

**Architecture:** One shared core pipeline powers three entrypoints: CLI, GitHub App worker, and manual GitHub Actions workflow. GitHub App mode uses API Gateway, Lambda, SQS, S3 quotas, Bedrock script generation, OpenAI TTS, and private S3 presigned URLs. Workflow mode is manual owner-only and uses repository secrets.

**Tech Stack:** Python 3.11, LangGraph, AWS Bedrock, OpenAI TTS, S3, GitHub App APIs, GitHub Actions, CDK.

---

## Milestone 1: Core dry-run pipeline

- command parser for `/podcast` and `/podcast focus <topic>`
- repo scanner with ignore rules
- focus-aware context pack builder
- structured script prompt builder
- CLI dry-run output
- unit tests

## Milestone 2: Script and audio generation

- Bedrock structured JSON generation
- Pydantic validation for duration, word count, and segments
- OpenAI TTS segment synthesis
- ffmpeg-based stitching, with raw concat fallback only if necessary
- local CLI end-to-end generation

## Milestone 3: Hosted GitHub App

- GitHub App manifest helper
- webhook Lambda signature verification
- repo/user allowlists
- S3 quota check and record
- SQS worker invocation
- GitHub comment rendering

## Milestone 4: Storage and cost controls

- S3 output bucket
- lifecycle expiration after 10 days
- presigned URLs
- cache by repo/ref/mode/focus/prompt version
- weekly per repo and global quota objects

## Milestone 5: Owner-only GitHub Action

- manual workflow_dispatch only
- owner guard
- dry-run default
- optional artifact upload
- docs for required secrets

## Milestone 6: Portfolio polish

- architecture diagram
- sample generated MP3
- README usage examples
- SECURITY.md
- demo issue with `/podcast focus langchain`
