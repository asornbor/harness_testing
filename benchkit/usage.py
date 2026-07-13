from __future__ import annotations
from typing import Any

def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def extract(value: Any) -> dict:
    result = {"input_tokens": None, "cached_input_tokens": None, "output_tokens": None, "reasoning_tokens": None}
    aliases = {
        "input_tokens": "input_tokens",
        "input_tokens_total": "input_tokens",
        "cache_read_input_tokens": "cached_input_tokens",
        "cached_input_tokens": "cached_input_tokens",
        "output_tokens": "output_tokens",
        "reasoning_tokens": "reasoning_tokens",
    }
    for obj in walk(value):
        usage = obj.get("usage") if isinstance(obj, dict) else None
        if not isinstance(usage, dict):
            continue
        for source, target in aliases.items():
            number = usage.get(source)
            if isinstance(number, int):
                result[target] = max(result[target] or 0, number)
        input_details = usage.get("input_tokens_details")
        if isinstance(input_details, dict) and isinstance(input_details.get("cached_tokens"), int):
            result["cached_input_tokens"] = max(result["cached_input_tokens"] or 0, input_details["cached_tokens"])
        output_details = usage.get("output_tokens_details")
        if isinstance(output_details, dict) and isinstance(output_details.get("reasoning_tokens"), int):
            result["reasoning_tokens"] = max(result["reasoning_tokens"] or 0, output_details["reasoning_tokens"])
    return result
