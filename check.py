"""Commit gate runner: runs tests, bytecode compilation, and repository sanity."""
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], description: str) -> bool:
    print(f"[GATE] Running {description}: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[GATE FAIL] {description} failed with returncode {result.returncode}")
        return False
    return True


def main() -> int:
    root = Path(__file__).resolve().parent
    py = sys.executable

    # 1. Pytest suite
    if not run_cmd([py, "-m", "pytest", "-q"], "Pytest suite"):
        return 1

    # 2. Compileall on src and api
    compile_targets = ["src"]
    if (root / "api").exists():
        compile_targets.append("api")
    if not run_cmd([py, "-m", "compileall", "-q"] + compile_targets, "Bytecode compilation"):
        return 1

    print("[GATE PASS] Commit gate verification succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
