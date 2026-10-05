import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    args = sys.argv[1:]
    target = [a for a in args if not a.startswith("-")] or ["api_tests"]
    options = [a for a in args if a.startswith("-")]
    workers = os.environ.get("QA_WORKERS", "4")
    command = [sys.executable, "-m", "pytest", *target, "-m", "api", "-q", "-n", workers, "--tb=short", *options]
    print(" ".join(command))
    code = subprocess.call(command, cwd=ROOT)
    subprocess.call([sys.executable, os.path.join("tools", "build_test_catalog.py")], cwd=ROOT)
    return code


if __name__ == "__main__":
    sys.exit(main())
