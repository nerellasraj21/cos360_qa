"""Read the Playwright JSON report (reports/ui-results*.json) into {case_id: [(outcome, reason)]}.

Outcomes use the pytest vocabulary so the catalog treats API and UI results the same way:
passed, failed, xfailed (test.fail and it failed: a known defect), xpassed (test.fail but it passed), skipped.
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(ROOT, "reports")
ID_RE = re.compile(r"TC-[A-Z]+-\d\d-E\d\d")


def _walk(suite):
    for spec in suite.get("specs", []):
        yield spec
    for child in suite.get("suites", []):
        yield from _walk(child)


def load() -> dict:
    """Latest result wins: reports are read oldest first and a later run of the same test replaces the earlier one."""
    latest = {}
    for path in sorted(glob.glob(os.path.join(REPORTS, "ui-results*.json")), key=os.path.getmtime):
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        run = {}
        _collect(data, run)
        for case_id, entries in run.items():
            for entry in entries:
                latest[(case_id, entry[2], entry[3])] = entry
    out = {}
    for (case_id, _, _), entry in latest.items():
        out.setdefault(case_id, []).append(entry[:3])
    return out


def _collect(data: dict, out: dict) -> None:
    for suite in data.get("suites", []):
        for spec in _walk(suite):
            ids = ID_RE.findall(spec.get("title", ""))
            for test in spec.get("tests", []):
                notes = {a.get("type"): a.get("description", "") for a in test.get("annotations", [])}
                results = test.get("results", [])
                final = results[-1]["status"] if results else "skipped"
                if test.get("status") == "skipped" or final == "skipped":
                    outcome, reason = "skipped", notes.get("skip", "")
                elif test.get("expectedStatus") == "failed":
                    outcome = "xfailed" if final in ("failed", "timedOut") else "xpassed"
                    reason = notes.get("fail", "")
                elif final == "passed":
                    outcome, reason = "passed", ""
                else:
                    outcome, reason = "failed", ""
                label = f"{test.get('projectName', '')}"
                for case_id in ids:
                    out.setdefault(case_id, []).append((outcome, reason, label, spec.get('title', '')))
