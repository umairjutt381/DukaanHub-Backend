from __future__ import annotations

from collections.abc import Mapping


SENSITIVE_KEYS = {
    "password",
    "pass",
    "token",
    "secret",
    "salt",
    "integrity_salt",
    "cvv",
    "otp",
    "pin",
    "card_number",
    "cardnumber",
}


def redact_payload(payload: Mapping[str, object] | None) -> dict[str, object]:
    if not payload:
        return {}
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        if any(sensitive in str(key).lower() for sensitive in SENSITIVE_KEYS):
            redacted[key] = "***REDACTED***"
        else:
            redacted[key] = value
    return redacted

