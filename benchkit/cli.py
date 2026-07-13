from __future__ import annotations
import argparse, json, shutil
from pathlib import Path
from .bootstrap import bootstrap
from .runner import smoke, pilot
from .reporting import write_report

ROOT = Path(__file__).resolve().parents[1]

def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("bootstrap"); boot.add_argument("--verify-only", action="store_true"); boot.add_argument("--skip-proxy", action="store_true")
    commands.add_parser("smoke")
    p = commands.add_parser("pilot"); p.add_argument("--harness", action="append", default=[]); p.add_argument("--fixture", action="append", default=["ttl_cache"]); p.add_argument("--repetitions", type=int, default=1); p.add_argument("--seed", type=int, default=1); p.add_argument("--results", type=Path, default=ROOT / "results" / "pilot"); p.add_argument("--no-subscription", action="store_true")
    r = commands.add_parser("report"); r.add_argument("--results", type=Path, default=ROOT / "results" / "pilot"); r.add_argument("--output", type=Path, default=ROOT / "results" / "report.json")
    commands.add_parser("clean")
    args = parser.parse_args(argv)
    if args.command == "bootstrap":
        manifest = bootstrap(install=not args.verify_only, with_proxy=not args.skip_proxy); print(json.dumps({"verified": [item["name"] for item in manifest]}, indent=2)); return 0
    if args.command == "smoke":
        rows = smoke(); failed = [row["harness"] for row in rows if row["exit_code"] or row["timed_out"]]; print(json.dumps({"harnesses": [row["harness"] for row in rows], "failed": failed}, indent=2)); return 1 if failed else 0
    if args.command == "pilot":
        harnesses = args.harness or (["deterministic"] if args.no_subscription else ["codex", "claude", "pi", "crush", "opencode"])
        rows = pilot(harnesses=harnesses, fixtures=args.fixture, repetitions=args.repetitions, seed=args.seed, results_root=args.results, no_subscription=args.no_subscription)
        print(json.dumps({"runs": len(rows), "results": str(args.results)}, indent=2)); return 0
    if args.command == "report":
        summary = write_report(args.results, args.output); print(json.dumps({"output": str(args.output), "warnings": summary["warnings"]}, indent=2)); return 0
    if args.command == "clean":
        for path in (ROOT / "results", ROOT / "artifacts", ROOT / ".toolchain", ROOT / "toolchain" / "node_modules"):
            if path.exists(): shutil.rmtree(path)
        return 0
    raise AssertionError(args.command)
