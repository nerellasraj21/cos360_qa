"""Write the latest API run results back into the Status column of the feature docs.

Only API rows (TC-...-A..) that have a result in reports/results-*.json are touched.
Unit and UI rows are left as they are. Run after tools/run_api_tests.py, then run
tools/sync_specs.py and tools/build_test_catalog.py.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
APP = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
FEATURES = os.path.join(APP, "docs", "features")
ROW_RE = re.compile(r"^\|\s*(TC-[A-Z]+-\d\d-A\d\d)\s*\|")
RANK = ("failed", "xpassed", "xfailed", "skipped", "passed")


def short(reason: str) -> str:
    reason = (reason or "").replace("|", "/").replace("`", "").strip()
    reason = re.sub(r"^(XFAIL|Skipped|SKIP|reason)[:\s]*", "", reason, flags=re.I)
    reason = re.sub(r"\s+", " ", reason)
    first = re.split(r"(?<=[.;])\s", reason, maxsplit=1)[0]
    return (first[:110] + "...") if len(first) > 113 else first


def load() -> dict:
    merged = {}
    for path in glob.glob(os.path.join(REPORTS, "results-*.json")):
        with open(path, encoding="utf-8") as handle:
            for entry in json.load(handle).values():
                for case_id in entry["tc"]:
                    merged.setdefault(case_id, []).append((entry["outcome"], entry.get("reason", "")))
    status = {}
    for case_id, outcomes in merged.items():
        for rank in RANK:
            hits = [r for o, r in outcomes if o == rank]
            if not hits:
                continue
            if rank == "passed":
                status[case_id] = "passing"
            elif rank in ("failed", "xpassed"):
                status[case_id] = "failing"
            elif rank == "xfailed":
                status[case_id] = f"known defect: {short(hits[0])}" if short(hits[0]) else "known defect"
            else:
                status[case_id] = f"skipped: {short(hits[0])}" if short(hits[0]) else "skipped"
            break
    return status


def main() -> None:
    status = load()
    if not status:
        sys.exit("No results in reports/results-*.json; run tools/run_api_tests.py first")
    changed = 0
    for path in sorted(glob.glob(os.path.join(FEATURES, "*.md"))):
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        touched = 0
        for i, line in enumerate(lines):
            match = ROW_RE.match(line)
            if not match or match.group(1) not in status:
                continue
            body = line.rstrip()
            if not body.endswith("|"):
                continue
            cut = body[:-1].rstrip().rfind("|")
            new = body[: cut + 1] + f" {status[match.group(1)]} |"
            if new != body:
                lines[i] = new
                touched += 1
        if touched:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write("\n".join(lines))
            changed += touched
            print(f"{os.path.basename(path)}: {touched} rows")
    print(f"{changed} API rows updated from {len(status)} results")


if __name__ == "__main__":
    main()
