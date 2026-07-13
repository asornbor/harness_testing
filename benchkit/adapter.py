from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .security import redact_text

CommandBuilder = Callable[[argparse.Namespace], tuple[list[str], str | None]]


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def parse_events(stdout: str) -> tuple[list[dict], list[dict], dict, str | None]:
    events: list[dict] = []
    tools: list[dict] = []
    usage: dict[str, int] = {}
    model = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        for obj in _walk(event):
            candidate_model = obj.get("model")
            if isinstance(candidate_model, str):
                model = candidate_model
            tool_name = obj.get("tool") or obj.get("name") if obj.get("type") in {"tool_call", "tool_use", "function_call"} else None
            if isinstance(tool_name, str):
                tools.append({"tool": tool_name, "event": obj})
            possible = obj.get("usage")
            if isinstance(possible, dict):
                for source, target in (
                    ("input_tokens", "input_tokens"),
                    ("cached_input_tokens", "cached_input_tokens"),
                    ("cache_read_input_tokens", "cached_input_tokens"),
                    ("output_tokens", "output_tokens"),
                    ("reasoning_tokens", "reasoning_tokens"),
                ):
                    value = possible.get(source)
                    if isinstance(value, int):
                        usage[target] = max(usage.get(target, 0), value)
                details = possible.get("input_tokens_details") or {}
                if isinstance(details.get("cached_tokens"), int):
                    usage["cached_input_tokens"] = max(usage.get("cached_input_tokens", 0), details["cached_tokens"])
                details = possible.get("output_tokens_details") or {}
                if isinstance(details.get("reasoning_tokens"), int):
                    usage["reasoning_tokens"] = max(usage.get("reasoning_tokens", 0), details["reasoning_tokens"])
    return events, tools, usage, model


def common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--result-dir", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--effort", required=True)
    parser.add_argument("--timeout", type=int, required=True)
    parser.add_argument("--base-url", required=True)
    return parser


def provider_env(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    key = env.get("BENCH_PROXY_API_KEY", "benchmark-local-only")
    env.update({
        "OPENAI_BASE_URL": args.base_url.rstrip("/") + "/v1",
        "OPENAI_API_BASE": args.base_url.rstrip("/") + "/v1",
        "OPENAI_API_KEY": key,
        "ANTHROPIC_BASE_URL": args.base_url.rstrip("/"),
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_API_KEY": key,
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "NO_COLOR": "1",
        "BENCH_MODEL": args.model,
        "BENCH_EFFORT": args.effort,
    })
    return env


def run_adapter(name: str, builder: CommandBuilder, binary: str, argv: list[str] | None = None) -> int:
    args = common_parser().parse_args(argv)
    if args.model != "gpt-5.6-sol" or args.effort != "high":
        raise SystemExit("benchmark contract requires gpt-5.6-sol with high effort")
    result_dir = Path(args.result_dir)
    result_dir.mkdir(parents=True, exist_ok=True)
    command, stdin = builder(args)
    if Path(command[0]).name != binary:
        raise SystemExit(f"{name}: expected genuine {binary} binary")
    started = time.time()
    try:
        completed = subprocess.run(
            command,
            input=stdin,
            cwd=Path(args.workspace),
            env=provider_env(args),
            text=True,
            capture_output=True,
            timeout=args.timeout,
            check=False,
        )
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "")
        timed_out = True
    ended = time.time()
    stdout = completed.stdout if isinstance(completed.stdout, str) else completed.stdout.decode(errors="replace")
    stderr = completed.stderr if isinstance(completed.stderr, str) else completed.stderr.decode(errors="replace")
    stdout = redact_text(stdout)
    stderr = redact_text(stderr)
    events, tools, usage, observed_model = parse_events(stdout)
    (result_dir / "stdout.jsonl").write_text(stdout, encoding="utf-8")
    (result_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    result = {
        "schema_version": 1,
        "harness": name,
        "command": command,
        "binary_sha256": hashlib.sha256(Path(command[0]).resolve().read_bytes()).hexdigest(),
        "requested_model": args.model,
        "observed_model": observed_model,
        "requested_effort": args.effort,
        "model_verified": observed_model in {None, args.model},
        "effort_verified": args.effort in command or any(args.effort in part for part in command),
        "started_at_unix": started,
        "ended_at_unix": ended,
        "wall_seconds": ended - started,
        "exit_code": completed.returncode,
        "timed_out": timed_out,
        "events": events,
        "tool_calls": tools,
        "usage": usage,
        "final_response": next((event.get("result") or event.get("text") for event in reversed(events) if event.get("result") or event.get("text")), None),
    }
    (result_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return completed.returncode
