from __future__ import annotations
import importlib.util, json, random, shutil, subprocess, tempfile, time, uuid
from pathlib import Path
from .fixtures import build_workspace, assert_isolated, fixture_path

ROOT = Path(__file__).resolve().parents[1]
IMAGE = "harness-benchmark:local"
ADAPTERS = ["codex", "claude", "pi", "crush", "opencode"]
MODEL = "gpt-5.6-sol"
EFFORT = "high"

def command(*args, check=True, capture=False):
    return subprocess.run(args, check=check, text=True, capture_output=capture)

def build_image():
    command("docker", "build", "-f", str(ROOT / "docker" / "harness.Dockerfile"), "-t", IMAGE, str(ROOT))

def _copy_from(container: str, source: str, destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    command("docker", "cp", f"{container}:{source}/.", str(destination))

def _load_grader(fixture: str):
    path = fixture_path(fixture) / "grader.py"
    spec = importlib.util.spec_from_file_location(f"{fixture}_grader", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module

def grade(fixture: str, workspace: Path) -> dict:
    return _load_grader(fixture).grade(workspace)

def normalize(adapter_result: dict, grade_result: dict, *, harness: str, fixture: str, repetition: int, seed: int, exit_state: str) -> dict:
    usage = adapter_result.get("usage") or {}
    usage_complete = all(isinstance(usage.get(k), int) for k in ("input_tokens", "output_tokens"))
    return {
        "schema_version": 1, "harness": harness, "fixture": fixture, "repetition": repetition, "seed": seed,
        "requested_model": adapter_result.get("requested_model", MODEL), "requested_effort": adapter_result.get("requested_effort", EFFORT),
        "observed_model": adapter_result.get("observed_model"), "usage_complete": usage_complete,
        "tool_calls": adapter_result.get("tool_calls", []), "tool_call_count": len(adapter_result.get("tool_calls", [])),
        "exit_code": adapter_result.get("exit_code"), "timed_out": adapter_result.get("timed_out", False), "exit_state": exit_state,
        "wall_seconds": adapter_result.get("wall_seconds"), "usage": usage, "score": grade_result.get("score", 0),
        "max_score": grade_result.get("max_score", 10), "grade_passed": grade_result.get("passed", False),
    }

def cells(harnesses: list[str], fixtures: list[str], repetitions: int, seed: int) -> list[tuple[str, str, int]]:
    out = [(h, f, r) for h in harnesses for f in fixtures for r in range(repetitions)]
    random.Random(seed).shuffle(out)
    return out

def _deterministic_run(workspace: Path, fixture: str, result_dir: Path) -> dict:
    shutil.copy2(fixture_path(fixture) / "reference" / "ttl_cache.py", workspace / "ttl_cache.py")
    started = time.time(); grade_result = grade(fixture, workspace); ended = time.time()
    result = {"harness": "deterministic", "requested_model": MODEL, "requested_effort": EFFORT, "observed_model": MODEL, "tool_calls": [], "usage": {}, "exit_code": 0, "timed_out": False, "wall_seconds": ended - started}
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result, grade_result

def pilot(*, harnesses: list[str], fixtures: list[str], repetitions: int, seed: int, results_root: Path | None = None, no_subscription: bool = False) -> list[dict]:
    results_root = results_root or ROOT / "results" / "pilot"
    results_root.mkdir(parents=True, exist_ok=True)
    rows = []
    real = [h for h in harnesses if h != "deterministic"]
    if real:
        build_image()
    suffix = uuid.uuid4().hex[:10]
    for harness, fixture, rep in cells(harnesses, fixtures, repetitions, seed):
        cell_dir = results_root / harness / fixture / str(rep)
        normalized_path = cell_dir / "result.normalized.json"
        if normalized_path.exists():
            rows.append(json.loads(normalized_path.read_text()))
            continue
        workspace = cell_dir / "workspace"
        build_workspace(fixture, workspace); assert_isolated(workspace)
        adapter_dir = cell_dir / "adapter"
        if harness == "deterministic":
            adapter_result, grade_result = _deterministic_run(workspace, fixture, adapter_dir)
            exit_state = "completed"
        else:
            if no_subscription:
                raise RuntimeError("no-subscription pilot only supports deterministic harness")
            container = f"bench-pilot-{harness}-{fixture}-{rep}-{suffix}"
            args = ["docker", "create", "--name", container, "--cpus", "2", "--memory", "4g", "--mount", f"type=bind,src={workspace},dst=/workspace", "--workdir", "/workspace", IMAGE, "python3", f"/opt/benchmark/adapters/{harness}.py", "--workspace", "/workspace", "--prompt-file", "/workspace/TASK.md", "--result-dir", "/tmp/result", "--model", MODEL, "--effort", EFFORT, "--timeout", "600", "--base-url", "http://127.0.0.1:9"]
            command(*args); completed = command("docker", "start", "-a", container, check=False, capture=True)
            _copy_from(container, "/tmp/result", adapter_dir); command("docker", "rm", "-f", container, check=False)
            adapter_result = json.loads((adapter_dir / "result.json").read_text())
            grade_result = grade(fixture, workspace)
            exit_state = "completed" if completed.returncode == 0 else "adapter_failed"
        norm = normalize(adapter_result, grade_result, harness=harness, fixture=fixture, repetition=rep, seed=seed, exit_state=exit_state)
        normalized_path.write_text(json.dumps(norm, indent=2) + "\n")
        with (results_root / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(norm) + "\n")
        rows.append(norm)
    return rows

def smoke(results_root: Path | None = None) -> list[dict]:
    results_root = results_root or ROOT / "results" / "smoke"; results_root.mkdir(parents=True, exist_ok=True); build_image()
    suffix = uuid.uuid4().hex[:10]; network = f"bench-{suffix}"; provider = f"bench-provider-{suffix}"; meter = f"bench-meter-{suffix}"
    command("docker", "network", "create", "--internal", network)
    try:
        command("docker", "run", "-d", "--name", provider, "--network", network, IMAGE, "python3", "-m", "benchkit.mock_server", "--listen", "0.0.0.0:8081")
        command("docker", "run", "-d", "--name", meter, "--network", network, IMAGE, "python3", "-m", "benchkit.proxy", "--listen", "0.0.0.0:8080", "--upstream", "http://"+provider+":8081", "--outdir", "/tmp/meter")
        time.sleep(1); rows = []
        for harness in ADAPTERS:
            with tempfile.TemporaryDirectory() as workspace_raw:
                workspace = Path(workspace_raw); (workspace / "TASK.md").write_text("Reply with exactly benchmark-ok. Do not use tools or modify files.\n")
                container = f"bench-run-{harness}-{suffix}"; dest = results_root / f"smoke-{harness}"
                args = ["docker", "create", "--name", container, "--network", network, "--cpus", "2", "--memory", "4g", "--mount", f"type=bind,src={workspace},dst=/workspace", "--workdir", "/workspace", IMAGE, "python3", f"/opt/benchmark/adapters/{harness}.py", "--workspace", "/workspace", "--prompt-file", "/workspace/TASK.md", "--result-dir", "/tmp/result", "--model", MODEL, "--effort", EFFORT, "--timeout", "180", "--base-url", "http://"+meter+":8080"]
                command(*args); completed = command("docker", "start", "-a", container, check=False, capture=True); _copy_from(container, "/tmp/result", dest); command("docker", "rm", "-f", container, check=False)
                result = json.loads((dest / "result.json").read_text()); result["container_exit_code"] = completed.returncode; rows.append(result)
        _copy_from(meter, "/tmp/meter", results_root / "meter"); return rows
    finally:
        command("docker", "rm", "-f", provider, meter, check=False); command("docker", "network", "rm", network, check=False)
