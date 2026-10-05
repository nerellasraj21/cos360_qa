import json
import os

import pytest

ROOT = os.path.dirname(os.path.abspath(__file__))
REPORTS = os.path.join(ROOT, "reports")

_results: dict = {}


def _worker() -> str:
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    ids = [marker.args[0] for marker in item.iter_markers("tc") if marker.args]
    entry = _results.setdefault(item.nodeid, {"tc": ids, "outcome": "passed", "reason": ""})
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        if hasattr(report, "wasxfail"):
            entry["outcome"] = "xfailed" if report.skipped else "xpassed"
            entry["reason"] = str(report.wasxfail)
        elif report.skipped:
            entry["outcome"] = "skipped"
            entry["reason"] = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else ""
        elif report.failed:
            entry["outcome"] = "failed"
        else:
            entry["outcome"] = "passed"


def pytest_sessionstart(session):
    if _worker() == "main" or os.environ.get("PYTEST_XDIST_WORKER") == "gw0":
        os.makedirs(REPORTS, exist_ok=True)
        for name in os.listdir(REPORTS):
            if name.startswith("results-") and name.endswith(".json"):
                try:
                    os.remove(os.path.join(REPORTS, name))
                except OSError:
                    pass


def pytest_sessionfinish(session, exitstatus):
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, f"results-{_worker()}.json"), "w", encoding="utf-8") as handle:
        json.dump(_results, handle, indent=1)
