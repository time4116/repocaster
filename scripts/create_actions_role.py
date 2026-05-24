#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from contextlib import suppress

import boto3


def _account_id() -> str:
    return boto3.client("sts").get_caller_identity()["Account"]


_INFERENCE_PROFILE_PREFIXES = ("us.", "eu.", "ap.", "global.")


def bedrock_model_resources(model_id: str, region: str, account: str = "") -> list[str]:
    """Return the list of ARNs that must be allowed for this model.

    Cross-region inference profiles (global.*, us.*, etc.) require both the
    inference-profile ARN and the underlying foundation-model ARN because
    Bedrock checks authorization against both when the Converse API is called.
    """
    if model_id.startswith("arn:aws"):
        parts = model_id.split(":", 5)
        if len(parts) != 6 or parts[2] != "bedrock":
            raise ValueError("Bedrock model ARN must be an arn:aws:*:bedrock ARN")
        if not parts[5].startswith(("foundation-model/", "inference-profile/")):
            raise ValueError(
                "Bedrock model ARN must reference a foundation model or inference profile"
            )
        return [model_id]
    if any(model_id.startswith(p) for p in _INFERENCE_PROFILE_PREFIXES):
        prefix = next(p for p in _INFERENCE_PROFILE_PREFIXES if model_id.startswith(p))
        base_model_id = model_id[len(prefix):]
        return [
            f"arn:aws:bedrock:{region}:{account}:inference-profile/{model_id}",
            f"arn:aws:bedrock:*::foundation-model/{base_model_id}",
        ]
    return [f"arn:aws:bedrock:*::foundation-model/{model_id}"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Create GitHub Actions OIDC role for Repocaster.")
    parser.add_argument("--owner", default="time4116")
    parser.add_argument("--repo", default="repocaster")
    parser.add_argument("--role-name", default="repocaster-actions")
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument(
        "--bedrock-model-id",
        required=True,
        help="Bedrock model ID or ARN to permit for InvokeModel.",
    )
    args = parser.parse_args()

    account = _account_id()
    iam = boto3.client("iam")
    provider_arn = f"arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com"
    with suppress(iam.exceptions.EntityAlreadyExistsException):
        iam.create_open_id_connect_provider(
            Url="https://token.actions.githubusercontent.com",
            ClientIDList=["sts.amazonaws.com"],
            ThumbprintList=["6938fd4d98bab03faadb97b34396831e3780aea1"],
        )

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Federated": provider_arn},
                "Action": "sts:AssumeRoleWithWebIdentity",
                "Condition": {
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": [
                            f"repo:{args.owner}/{args.repo}:ref:refs/heads/main",
                            f"repo:{args.owner}/{args.repo}:environment:*",
                        ]
                    },
                },
            }
        ],
    }

    try:
        role = iam.create_role(
            RoleName=args.role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Owner-only Repocaster GitHub Actions role",
        )["Role"]
    except iam.exceptions.EntityAlreadyExistsException:
        iam.update_assume_role_policy(
            RoleName=args.role_name,
            PolicyDocument=json.dumps(trust_policy),
        )
        role = iam.get_role(RoleName=args.role_name)["Role"]

    bedrock_resources = bedrock_model_resources(args.bedrock_model_id, args.region, account)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                "Resource": bedrock_resources,
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
                "Resource": [
                    f"arn:aws:s3:::{args.bucket}",
                    f"arn:aws:s3:::{args.bucket}/*",
                ],
            },
        ],
    }
    iam.put_role_policy(
        RoleName=args.role_name,
        PolicyName="repocaster-actions-inline",
        PolicyDocument=json.dumps(policy),
    )
    print(
        json.dumps(
            {"role_arn": role["Arn"], "bucket": args.bucket, "bedrock_resources": bedrock_resources},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
