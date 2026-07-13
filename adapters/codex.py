#!/usr/bin/env python3
from pathlib import Path
from benchkit.adapter import run_adapter

def build(args):
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    return (["codex", "exec", "--json", "--model", args.model, "-c", f'model_reasoning_effort="{args.effort}"', "--skip-git-repo-check", "-"], prompt)

if __name__ == "__main__":
    raise SystemExit(run_adapter("codex", build, "codex"))
