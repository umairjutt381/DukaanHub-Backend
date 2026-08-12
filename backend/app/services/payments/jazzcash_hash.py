from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping


def build_jazzcash_secure_hash(payload: Mapping[str, object], integrity_salt: str) -> str:
    parts = [str(payload[key]) for key in sorted(payload.keys()) if key != "pp_SecureHash"]
    data = "&".join(parts)
    digest = hmac.new(integrity_salt.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest().upper()


def verify_jazzcash_secure_hash(payload: Mapping[str, object], integrity_salt: str, provided_hash: str) -> bool:
    expected = build_jazzcash_secure_hash(payload, integrity_salt)
    return hmac.compare_digest(expected.upper(), provided_hash.upper())

