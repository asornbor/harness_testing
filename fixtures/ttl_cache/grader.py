from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def grade(workspace: Path) -> dict:
    with tempfile.TemporaryDirectory() as raw:
        run = Path(raw)
        for item in workspace.iterdir():
            if item.name in {"hidden_tests", "reference"}:
                continue
            dest = run / item.name
            shutil.copytree(item, dest) if item.is_dir() else shutil.copy2(item, dest)
        tests = run / "tests"
        tests.mkdir()
        shutil.copytree(ROOT / "public_tests", tests / "public", dirs_exist_ok=True)
        shutil.copytree(ROOT / "hidden_tests", tests / "hidden", dirs_exist_ok=True)
        completed = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], cwd=run, text=True, capture_output=True, timeout=30)
    passed = completed.returncode == 0
    return {"score": 10 if passed else 0, "max_score": 10, "passed": passed, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:]}

if __name__ == "__main__":
    result = grade(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
