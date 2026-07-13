from __future__ import annotations
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
PUBLIC_NAMES = {"TASK.md", "starter", "public_tests"}

def fixture_path(name: str) -> Path:
    path = FIXTURES / name
    if not path.is_dir():
        raise ValueError(f"unknown fixture: {name}")
    return path

def build_workspace(name: str, destination: Path) -> Path:
    source = fixture_path(name)
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    shutil.copy2(source / "TASK.md", destination / "TASK.md")
    for item in (source / "starter").iterdir():
        target = destination / item.name
        shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)
    shutil.copytree(source / "public_tests", destination / "public_tests")
    return destination

def assert_isolated(workspace: Path) -> None:
    forbidden = {"hidden_tests", "reference", "grader.py"}
    exposed = [p for p in workspace.rglob("*") if any(part in forbidden for part in p.parts)]
    if exposed:
        raise RuntimeError(f"private fixture material exposed: {exposed}")
