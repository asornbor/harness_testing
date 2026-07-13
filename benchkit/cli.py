from __future__ import annotations
import argparse
import json
import shutil
from pathlib import Path
from .bootstrap import bootstrap
from .runner import smoke

ROOT = Path(__file__).resolve().parents[1]

def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("bootstrap")
    boot.add_argument("--verify-only", action="store_true")
    boot.add_argument("--skip-proxy", action="store_true")
    commands.add_parser("smoke")
    commands.add_parser("clean")
    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        manifest = bootstrap(install=not args.verify_only, with_proxy=not args.skip_proxy)
        print(json.dumps({"verified": [item["name"] for item in manifest]}, indent=2))
        return 0
    if args.command == "smoke":
        rows = smoke()
        failed = [row["harness"] for row in rows if row["exit_code"] or row["timed_out"]]
        print(json.dumps({"harnesses": [row["harness"] for row in rows], "failed": failed}, indent=2))
        return 1 if failed else 0
    if args.command == "clean":
        for path in (ROOT / "results", ROOT / "artifacts", ROOT / ".toolchain", ROOT / "toolchain" / "node_modules"):
            if path.exists():
                shutil.rmtree(path)
        return 0
    raise AssertionError(args.command)
