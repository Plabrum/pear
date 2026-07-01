"""Lambda webhook forwarder — S3 event → backend /webhooks/comms/email/inbound.

No dependencies beyond stdlib: deploys as a single zip with no layer.
"""

import hashlib
import hmac
import json
import os
import urllib.parse
import urllib.request


def lambda_handler(event, context):
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    # S3 URL-encodes keys with spaces/special chars — decode back to the real key
    s3_key = urllib.parse.unquote_plus(record["object"]["key"])

    payload = json.dumps({"bucket": bucket, "s3_key": s3_key}).encode()
    sig = hmac.new(
        os.environ["WEBHOOK_SECRET"].encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    req = urllib.request.Request(
        os.environ["WEBHOOK_URL"],
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Signature": sig,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status >= 500:
            raise RuntimeError(f"Backend returned {resp.status} — Lambda will retry")

    return {"statusCode": 200}
