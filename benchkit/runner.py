from __future__ import annotations
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "harness-benchmark:local"
ADAPTERS = ["codex", "claude", "pi", "crush", "opencode"]

def command(*args, check=True, capture=False):
    return subprocess.run(args, check=check, text=True, capture_output=capture)

def build_image():
    command("docker", "build", "-f", str(ROOT / "docker" / "harness.Dockerfile"), "-t", IMAGE, str(ROOT))

def _copy_from(container: str, source: str, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    command("docker", "cp", f"{container}:{source}/.", str(destination))

def smoke(results_root: Path | None = None) -> list[dict]:
    results_root = results_root or ROOT / "results" / "smoke"
    results_root.mkdir(parents=True, exist_ok=True)
    build_image()
    suffix = uuid.uuid4().hex[:10]
    network = f"bench-{suffix}"
    provider = f"bench-provider-{suffix}"
    meter = f"bench-meter-{suffix}"
    command("docker", "network", "create", "--internal", network)
    try:
        command("docker", "run", "-d", "--name", provider, "--network", network, IMAGE, "python3", "-m", "benchkit.mock_server", "--listen", "0.0.0.0:8081")
        command("docker", "run", "-d", "--name", meter, "--network", network, IMAGE, "python3", "-m", "benchkit.proxy", "--listen", "0.0.0.0:8080", "--upstream", "http://"+provider+":8081", "--outdir", "/tmp/meter")
        time.sleep(1)
        rows = []
        for harness in ADAPTERS:
            run_id = f"smoke-{harness}"
            with tempfile.TemporaryDirectory() as workspace_raw:
                workspace = Path(workspace_raw)
                (workspace / "TASK.md").write_text("Reply with exactly benchmark-ok. Do not use tools or modify files.\n", encoding="utf-8")
                container = f"bench-run-{harness}-{suffix}"
                args = [
                    "docker", "create", "--name", container, "--network", network, "--cpus", "2", "--memory", "4g",
                    "--mount", f"type=bind,src={workspace},dst=/workspace",
                    "--workdir", "/workspace", IMAGE, "python3", f"/opt/benchmark/adapters/{harness}.py",
                    "--workspace", "/workspace", "--prompt-file", "/workspace/TASK.md", "--result-dir", "/tmp/result",
                    "--model", "gpt-5.6-sol", "--effort", "high", "--timeout", "180", "--base-url", "http://"+meter+":8080",
                ]
                command(*args)
                completed = command("docker", "start", "-a", container, check=False, capture=True)
                destination = results_root / run_id
                _copy_from(container, "/tmp/result", destination)
                command("docker", "rm", "-f", container, check=False)
                result = json.loads((destination / "result.json").read_text(encoding="utf-8"))
                result["container_exit_code"] = completed.returncode
                rows.append(result)
        _copy_from(meter, "/tmp/meter", results_root / "meter")
        return rows
    finally:
        command("docker", "rm", "-f", provider, meter, check=False)
        command("docker", "network", "rm", network, check=False)
