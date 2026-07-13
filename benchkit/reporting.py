from __future__ import annotations
import json, statistics
from pathlib import Path

USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens", "credits")

def load_results(path: Path) -> list[dict]:
    if path.is_dir():
        files = sorted(path.rglob("result.normalized.json"))
        return [json.loads(f.read_text()) for f in files]
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def summarize(rows: list[dict]) -> dict:
    by = {}
    warnings = []
    for row in rows:
        by.setdefault(row["harness"], []).append(row)
    harnesses = {}
    for name, items in by.items():
        scores = [i.get("score", 0) for i in items]
        successes = [s for s in scores if s > 0]
        usage_complete = all(i.get("usage_complete") for i in items)
        if not usage_complete:
            warnings.append(f"{name}: usage incomplete; efficiency values unavailable where measured usage is absent")
        total_score = sum(scores)
        seconds = sum(i.get("wall_seconds") or 0 for i in items)
        usage = {k: None for k in USAGE_KEYS}
        if usage_complete:
            for key in USAGE_KEYS:
                vals = [i.get("usage", {}).get(key) for i in items]
                usage[key] = sum(vals) if vals and all(isinstance(v, (int, float)) for v in vals) else None
        spp = seconds / total_score if total_score else None
        harnesses[name] = {
            "runs": len(items), "success_score": total_score, "mean_score": statistics.mean(scores) if scores else 0,
            "reliability": len(successes) / len(items) if items else 0,
            "score_variance": statistics.pvariance(scores) if len(scores) > 1 else 0,
            "seconds_per_success_point": spp, "usage": usage, "tokens_per_success_point": None,
            "credits_per_success_point": None, "usage_complete": usage_complete,
        }
        token_total = None if usage["input_tokens"] is None or usage["output_tokens"] is None else usage["input_tokens"] + usage["output_tokens"]
        if token_total is not None and total_score:
            harnesses[name]["tokens_per_success_point"] = token_total / total_score
        if usage["credits"] is not None and total_score:
            harnesses[name]["credits_per_success_point"] = usage["credits"] / total_score
    success_rank = sorted(harnesses, key=lambda h: harnesses[h]["success_score"], reverse=True)
    efficiency_rank = sorted(harnesses, key=lambda h: (harnesses[h]["seconds_per_success_point"] is None, harnesses[h]["seconds_per_success_point"] or 10**9))
    reliability_rank = sorted(harnesses, key=lambda h: harnesses[h]["reliability"], reverse=True)
    frontier = []
    for h, m in harnesses.items():
        dominated = any(o != h and harnesses[o]["success_score"] >= m["success_score"] and harnesses[o]["reliability"] >= m["reliability"] and (harnesses[o]["seconds_per_success_point"] or 10**9) <= (m["seconds_per_success_point"] or 10**9) for o in harnesses)
        if not dominated: frontier.append(h)
    return {"harnesses": harnesses, "rankings": {"success": success_rank, "efficiency": efficiency_rank, "reliability": reliability_rank}, "pareto_frontier": sorted(frontier), "warnings": warnings}

def write_report(results: Path, output: Path) -> dict:
    summary = summarize(load_results(results))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n")
    return summary
