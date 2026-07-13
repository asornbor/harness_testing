from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "harnesses.json"
TOOLCHAIN = ROOT / "toolchain"
LOCAL = ROOT / ".toolchain"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def verify_npm_lock(config: dict) -> None:
    lock_path = TOOLCHAIN / "package-lock.json"
    if not lock_path.exists():
        raise RuntimeError("toolchain/package-lock.json is required; run the lock workflow")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    root_dependencies = lock["packages"][""]["dependencies"]
    for name, item in config["node_harnesses"].items():
        package = item["package"]
        expected = item["version"]
        if root_dependencies.get(package) != expected:
            raise RuntimeError(f"{name}: lock root is not pinned to {package}@{expected}")
        entry = lock["packages"].get(f"node_modules/{package}")
        if not entry or entry.get("version") != expected or not entry.get("integrity"):
            raise RuntimeError(f"{name}: immutable npm integrity entry is missing")


def npm_install() -> None:
    subprocess.run(["npm", "ci", "--prefix", str(TOOLCHAIN), "--no-audit", "--no-fund"], check=True)


def probe(binary: Path, name: str) -> dict:
    resolved = binary.resolve()
    if "tools/harnesses" in resolved.as_posix():
        raise RuntimeError(f"{name}: repository wrapper binaries are forbidden")
    version = subprocess.run([str(binary), "--version"], text=True, capture_output=True, timeout=30)
    help_result = subprocess.run([str(binary), "--help"], text=True, capture_output=True, timeout=30)
    if version.returncode or help_result.returncode:
        raise RuntimeError(f"{name}: version/help probe failed")
    return {
        "name": name,
        "launcher": str(binary.relative_to(ROOT)),
        "resolved_path": str(resolved),
        "resolved_sha256": digest(resolved),
        "reported_version": version.stdout.strip() or version.stderr.strip(),
        "help_sha256": hashlib.sha256((help_result.stdout + help_result.stderr).encode()).hexdigest(),
        "help": (help_result.stdout + help_result.stderr)[:20000],
    }


def install_cliproxy(config: dict) -> dict:
    meta = config["cliproxyapi"]
    version = meta["version"]
    asset = meta["linux_amd64_asset"]
    base = f"https://github.com/router-for-me/CLIProxyAPI/releases/download/v{version}"
    LOCAL.mkdir(exist_ok=True)
    bindir = LOCAL / "bin"
    bindir.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        checksums = temp / "checksums.txt"
        archive = temp / asset
        urllib.request.urlretrieve(f"{base}/checksums.txt", checksums)
        urllib.request.urlretrieve(f"{base}/{asset}", archive)
        expected = None
        for line in checksums.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) >= 2 and fields[-1].lstrip("*") == asset:
                expected = fields[0]
                break
        if not expected:
            raise RuntimeError(f"CLIProxyAPI checksum missing for {asset}")
        actual = digest(archive)
        if actual != expected:
            raise RuntimeError(f"CLIProxyAPI checksum mismatch: {actual} != {expected}")
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(temp / "extract", filter="data")
        candidates = [p for p in (temp / "extract").rglob("*") if p.is_file() and p.name.lower() in {"cliproxyapi", "cli-proxy-api"}]
        if len(candidates) != 1:
            raise RuntimeError(f"expected one CLIProxyAPI binary, found {len(candidates)}")
        destination = bindir / "cliproxyapi"
        shutil.copy2(candidates[0], destination)
        destination.chmod(0o755)
    version_result = subprocess.run([str(destination), "--version"], text=True, capture_output=True, timeout=30)
    if version_result.returncode:
        version_result = subprocess.run([str(destination), "-version"], text=True, capture_output=True, timeout=30)
    return {
        "name": "cliproxyapi",
        "version": version,
        "asset": asset,
        "sha256": digest(destination),
        "reported_version": (version_result.stdout + version_result.stderr).strip(),
    }


def bootstrap(*, install: bool = True, with_proxy: bool = True) -> list[dict]:
    config = load_config()
    verify_npm_lock(config)
    if install:
        npm_install()
    manifest = []
    bin_dir = TOOLCHAIN / "node_modules" / ".bin"
    for name, meta in config["node_harnesses"].items():
        binary = bin_dir / meta["binary"]
        if not binary.exists():
            raise RuntimeError(f"{name}: genuine package binary not installed at {binary}")
        package_json = TOOLCHAIN / "node_modules" / Path(meta["package"]) / "package.json"
        installed = json.loads(package_json.read_text(encoding="utf-8"))["version"]
        if installed != meta["version"]:
            raise RuntimeError(f"{name}: installed {installed}, expected {meta['version']}")
        item = probe(binary, name)
        item.update({"package": meta["package"], "expected_version": meta["version"], "package_json_sha256": digest(package_json)})
        manifest.append(item)
    if with_proxy:
        manifest.append(install_cliproxy(config))
    out = ROOT / "artifacts" / "versions"
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--skip-proxy", action="store_true")
    args = parser.parse_args(argv)
    result = bootstrap(install=not args.verify_only, with_proxy=not args.skip_proxy)
    print(json.dumps({"verified": [item["name"] for item in result]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
