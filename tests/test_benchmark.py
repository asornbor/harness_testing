import json, shutil, subprocess, sys
from pathlib import Path
from benchkit.fixtures import build_workspace
from benchkit.runner import cells, grade, normalize, pilot
from benchkit.reporting import summarize
from adapters.codex import build as codex_build
from adapters.claude import build as claude_build

ROOT = Path(__file__).resolve().parents[1]

class Args:
    workspace = "."; prompt_file = "TASK.md"; model = "gpt-5.6-sol"; effort = "high"

def test_package_importable_from_root():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, text=True, capture_output=True, timeout=60)
    assert out.returncode == 0, out.stderr

def test_fixture_isolation_and_grading(tmp_path):
    ws = build_workspace("ttl_cache", tmp_path / "ws")
    assert (ws / "TASK.md").exists() and (ws / "ttl_cache.py").exists() and (ws / "public_tests").exists()
    assert not (ws / "hidden_tests").exists() and not (ws / "reference").exists()
    starter = grade("ttl_cache", ws)
    assert starter["score"] == 0
    shutil.copy2(ROOT / "fixtures" / "ttl_cache" / "reference" / "ttl_cache.py", ws / "ttl_cache.py")
    assert grade("ttl_cache", ws)["score"] == 10

def test_adapter_flags_preserve_model_effort(tmp_path):
    prompt = tmp_path / "TASK.md"; prompt.write_text("x")
    args = Args(); args.prompt_file = str(prompt)
    assert "gpt-5.6-sol" in codex_build(args)[0]
    assert any('model_reasoning_effort="high"' == p for p in codex_build(args)[0])
    assert "--permission-mode" in claude_build(args)[0]

def test_normalization_usage_completeness():
    norm = normalize({"usage": {"input_tokens": 1, "output_tokens": 2}, "tool_calls": [{"tool":"x"}], "exit_code": 0}, {"score": 10, "passed": True}, harness="h", fixture="f", repetition=0, seed=4, exit_state="completed")
    assert norm["usage_complete"] is True and norm["tool_call_count"] == 1 and norm["score"] == 10

def test_deterministic_randomization_and_resumption(tmp_path):
    assert cells(["a","b"], ["f"], 2, 9) == cells(["a","b"], ["f"], 2, 9)
    rows1 = pilot(harnesses=["deterministic"], fixtures=["ttl_cache"], repetitions=1, seed=7, results_root=tmp_path, no_subscription=True)
    rows2 = pilot(harnesses=["deterministic"], fixtures=["ttl_cache"], repetitions=1, seed=7, results_root=tmp_path, no_subscription=True)
    assert rows1 == rows2 and rows1[0]["score"] == 10

def test_reporting_rankings_and_unavailable_usage():
    summary = summarize([
        {"harness":"a", "score":10, "wall_seconds":5, "usage_complete":True, "usage":{"input_tokens":10,"output_tokens":5}},
        {"harness":"b", "score":0, "wall_seconds":1, "usage_complete":False, "usage":{}},
    ])
    assert summary["rankings"]["success"][0] == "a"
    assert summary["harnesses"]["b"]["tokens_per_success_point"] is None
    assert summary["warnings"]

def test_banned_terms_absent_in_runtime_code():
    banned = ["harness_sim", "mock execution"]
    for path in [*ROOT.glob("benchkit/*.py"), *ROOT.glob("adapters/*.py")]:
        text = path.read_text()
        assert not any(term in text for term in banned)
