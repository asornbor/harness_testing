import re
from collections.abc import Mapping

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}
TOKEN_PATTERNS = (
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)

def redact_text(value: str) -> str:
    text = value
    for pattern in TOKEN_PATTERNS:
        text = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", text)
    return text

def safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {k: redact_text(v) for k, v in headers.items() if k.lower() not in SENSITIVE_HEADERS}
