"""
Lambda function that chunks text files.

Supports two invocation modes:

1. EVENT-DRIVEN (S3 trigger):
   Triggered automatically when files are uploaded to s3://bucket/input/.
   Output written to s3://bucket/output/.

2. MANUAL INVOKE (direct invocation):
   Called with a custom payload like:
     {"mode": "manual", "bucket": "...", "keys": ["input/a.txt", "input/b.txt"]}
   or:
     {"mode": "manual", "bucket": "...", "prefix": "input/"}  # process whole prefix
   or:
     {"mode": "manual", "text": "raw text to chunk"}  # no S3 at all
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "output/")


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """Split text into overlapping chunks, preferring sentence/word boundaries."""
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    idx = 0
    n = len(text)

    while start < n:
        end = min(start + size, n)
        if end < n:
            window_start = start + int(size * 0.8)
            slice_ = text[window_start:end]
            match = None
            for pattern in (r"[.!?]\s", r"\n", r"\s"):
                m = list(re.finditer(pattern, slice_))
                if m:
                    match = m[-1]
                    break
            if match:
                end = window_start + match.end()

        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "index": idx,
                "start": start,
                "end": end,
                "char_count": len(chunk),
                "text": chunk,
            })
            idx += 1

        if end >= n:
            break
        start = max(end - overlap, start + 1)

    return chunks


def process_s3_object(bucket: str, key: str) -> dict:
    """Read a file from S3, chunk it, write chunks back to S3."""
    logger.info("Processing s3://%s/%s", bucket, key)
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read().decode("utf-8", errors="replace")
    chunks = chunk_text(body)

    payload = {
        "source_bucket": bucket,
        "source_key": key,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "original_char_count": len(body),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "chunk_count": len(chunks),
        "chunks": chunks,
    }

    out_bucket = OUTPUT_BUCKET or bucket
    base = os.path.basename(key).rsplit(".", 1)[0]
    out_key = f"{OUTPUT_PREFIX}{base}.chunks.json"

    s3.put_object(
        Bucket=out_bucket,
        Key=out_key,
        Body=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Wrote %d chunks to s3://%s/%s", len(chunks), out_bucket, out_key)
    return {
        "key": key,
        "status": "ok",
        "chunk_count": len(chunks),
        "output": f"s3://{out_bucket}/{out_key}",
    }


def handle_s3_event(event: dict) -> list[dict]:
    """Process an S3 ObjectCreated event (event-driven mode)."""
    results = []
    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        try:
            results.append(process_s3_object(bucket, key))
        except Exception as exc:
            logger.exception("Failed on s3://%s/%s", bucket, key)
            results.append({"key": key, "status": "error", "error": str(exc)})
    return results


def handle_manual_invoke(event: dict) -> list[dict]:
    """Process a manual invocation (custom payload).

    Accepted shapes:
      {"text": "..."}                              -> chunk raw text, return inline
      {"bucket": "...", "keys": ["k1", "k2"]}      -> process specific S3 keys
      {"bucket": "...", "prefix": "input/"}        -> process all objects under prefix
    """
    # Inline text mode (no S3 at all, useful for quick tests)
    if "text" in event:
        chunks = chunk_text(event["text"])
        return [{
            "status": "ok",
            "source": "inline",
            "chunk_count": len(chunks),
            "chunks": chunks,
        }]

    bucket = event.get("bucket") or OUTPUT_BUCKET
    if not bucket:
        raise ValueError("manual invoke needs either 'text' or 'bucket'")

    # Explicit list of keys
    keys = event.get("keys")
    if not keys:
        # Or: list everything under prefix
        prefix = event.get("prefix", "input/")
        logger.info("Listing s3://%s/%s", bucket, prefix)
        paginator = s3.get_paginator("list_objects_v2")
        keys = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".txt"):
                    keys.append(obj["Key"])
        logger.info("Found %d files to process", len(keys))

    results = []
    for key in keys:
        try:
            results.append(process_s3_object(bucket, key))
        except Exception as exc:
            logger.exception("Failed on s3://%s/%s", bucket, key)
            results.append({"key": key, "status": "error", "error": str(exc)})
    return results


def lambda_handler(event, context):
    """Route the event to the right handler based on its shape."""
    # S3 event has "Records" with "s3" inside each
    is_s3_event = (
        isinstance(event, dict)
        and "Records" in event
        and event["Records"]
        and "s3" in event["Records"][0]
    )

    if is_s3_event:
        logger.info("Mode: event-driven (S3 trigger)")
        results = handle_s3_event(event)
    else:
        logger.info("Mode: manual invoke")
        results = handle_manual_invoke(event)

    return {
        "statusCode": 200,
        "mode": "s3_event" if is_s3_event else "manual",
        "processed": len(results),
        "results": results,
    }
