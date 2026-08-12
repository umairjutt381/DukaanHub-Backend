from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping


def build_easypaisa_signature(payload: Mapping[str, object], hash_key: str) -> str:
    parts = [str(payload[key]) for key in sorted(payload.keys()) if key not in {"hash", "signature"}]
    data = "&".join(parts)
    digest = hmac.new(hash_key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest().upper()


def verify_easypaisa_signature(payload: Mapping[str, object], hash_key: str, provided_signature: str) -> bool:
    expected = build_easypaisa_signature(payload, hash_key)
    return hmac.compare_digest(expected.upper(), provided_signature.upper())

