#!/usr/bin/env python3
from pathlib import Path
from benchkit.adapter import run_adapter

def build(args):
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    return (["pi", "--mode", "json", "--provider", "openai", "--model", args.model, "--thinking", args.effort, "--no-session", "-p", prompt], None)

if __name__ == "__main__":
    raise SystemExit(run_adapter("pi", build, "pi"))
