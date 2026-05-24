#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from contextlib import suppress

import boto3


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create/configure the Repocaster S3 output bucket."
    )
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--retention-days", type=int, default=10)
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    create_args = {"Bucket": args.bucket}
    if args.region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": args.region}
    with suppress(s3.exceptions.BucketAlreadyOwnedByYou):
        s3.create_bucket(**create_args)

    s3.put_public_access_block(
        Bucket=args.bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    s3.put_bucket_encryption(
        Bucket=args.bucket,
        ServerSideEncryptionConfiguration={
            "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
        },
    )
    s3.put_bucket_lifecycle_configuration(
        Bucket=args.bucket,
        LifecycleConfiguration={
            "Rules": [
                {
                    "ID": "expire-generated-repocaster-output",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Expiration": {"Days": args.retention_days},
                    "AbortIncompleteMultipartUpload": {"DaysAfterInitiation": 1},
                }
            ]
        },
    )
    print(json.dumps({"bucket": args.bucket, "retention_days": args.retention_days}, indent=2))


if __name__ == "__main__":
    main()
