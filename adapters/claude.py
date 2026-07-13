#!/usr/bin/env python3
from pathlib import Path
from benchkit.adapter import run_adapter

def build(args):
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    return (["claude", "--print", "--output-format", "stream-json", "--verbose", "--model", args.model, "--permission-mode", "bypassPermissions", "--no-session-persistence"], prompt)

if __name__ == "__main__":
    raise SystemExit(run_adapter("claude", build, "claude"))
