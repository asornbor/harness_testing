import json
from benchkit.security import redact_text, safe_headers
from benchkit.usage import extract

def test_redaction_omits_credentials():
    assert "secret" not in redact_text("Authorization: Bearer secret")
    assert safe_headers({"Authorization": "Bearer secret", "Content-Type": "application/json"}) == {"Content-Type": "application/json"}

def test_usage_preserves_unavailable_and_reasoning():
    value = {"response": {"usage": {"input_tokens": 10, "output_tokens": 8, "input_tokens_details": {"cached_tokens": 3}, "output_tokens_details": {"reasoning_tokens": 4}}}}
    assert extract(value) == {"input_tokens": 10, "cached_input_tokens": 3, "output_tokens": 8, "reasoning_tokens": 4}
    assert extract({"status": "ok"}) == {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None, "reasoning_tokens": None}
