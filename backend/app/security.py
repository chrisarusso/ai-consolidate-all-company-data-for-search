import hmac
import time
from hashlib import sha256
from typing import Optional


def verify_hmac_signature(body: bytes, signature: str, secret: str) -> bool:
    """
    Generic HMAC-SHA256 verification used for Fathom-style webhooks.
    """
    digest = hmac.new(secret.encode(), body, sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def verify_slack_signature(
    timestamp: str,
    signature: str,
    body: bytes,
    secret: str,
    tolerance_seconds: int = 300,
) -> bool:
    """
    Minimal Slack signing verification (v0).
    """
    try:
        req_ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - req_ts) > tolerance_seconds:
        return False
    base = f"v0:{timestamp}:{body.decode()}".encode()
    digest = hmac.new(secret.encode(), base, sha256).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, signature)

