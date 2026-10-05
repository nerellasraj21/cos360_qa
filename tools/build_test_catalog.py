import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS = os.path.join(ROOT, "test_specs")
REPORTS = os.path.join(ROOT, "reports")
OUT_XLSX = os.path.join(ROOT, "test_cases", "COS360_Test_Cases.xlsx")
OUT_CSV = os.path.join(ROOT, "test_cases", "COS360_Test_Cases.csv")

PHASES = {"U": "Unit", "A": "API", "E": "UI"}
ID_RE = re.compile(r"TC-[A-Z]+-\d\d-[UAE]\d\d")
FEATURE_RE = re.compile(r"^##\s+(F\d\d)\s+(.*)$")
ROW_RE = re.compile(r"^\|\s*(TC-[A-Z]+-\d\d-[UAE]\d\d)\s*\|")
MODULE_TITLES = {
    "auth": "Authentication",
    "tenants-and-admin": "Tenants and Admin",
    "masters": "Masters",
    "timetable-calendar": "Timetable and Calendar",
    "students": "Students",
    "certificates": "Certificates",
    "staff": "Staff",
    "communication": "Communication",
    "fee": "Fee",
    "exam": "Exam",
    "expense": "Expense",
    "transport": "Transport",
    "reports-dashboards": "Reports and Dashboards",
}


def split_row(line: str) -> list:
    cells, current, in_code = [], [], False
    for char in line.strip().strip("|"):
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def clean(text: str) -> str:
    return text.replace("`", "").replace("\\|", "|").strip()


def read_specs() -> list:
    rows = []
    for path in sorted(glob.glob(os.path.join(SPECS, "*.md"))):
        name = os.path.splitext(os.path.basename(path))[0]
        if name.startswith("_") or name.upper() == "README":
            continue
        module = MODULE_TITLES.get(name, name)
        feature = ""
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                feature_match = FEATURE_RE.match(line)
                if feature_match:
                    feature = f"{feature_match.group(1)} {feature_match.group(2).strip()}"
                    continue
                if not ROW_RE.match(line):
                    continue
                cells = [clean(cell) for cell in split_row(line)]
                case_id = cells[0]
                code = case_id.split("-")[1]
                rows.append(
                    {
                        "id": case_id,
                        "module": module,
                        "module_code": code,
                        "feature": feature,
                        "phase": PHASES[case_id[-3]],
                        "scenario": cells[1] if len(cells) > 1 else "",
                        "expected": cells[2] if len(cells) > 2 else "",
                        "doc_status": cells[3] if len(cells) > 3 else "",
                        "doc": os.path.basename(path),
                    }
                )
    return rows


def find_automation() -> dict:
    roots = [os.path.join(ROOT, "api_tests"), os.path.join(ROOT, "ui_tests", "tests")]
    app = os.environ.get("COS360_APP") or os.path.join(os.path.dirname(ROOT), "COS360_Full_App")
    for relative in ("backend/tests/unit", "web/src/__tests__", "mobile/__tests__"):
        candidate = os.path.join(app, relative)
        if os.path.isdir(candidate):
            roots.append(candidate)
    found = defaultdict(set)
    for base in roots:
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in {"node_modules", "__pycache__"}]
            for filename in filenames:
                if not filename.endswith((".py", ".js", ".ts", ".tsx")):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
                for case_id in set(ID_RE.findall(text)):
                    found[case_id].add(os.path.relpath(path, os.path.dirname(ROOT)).replace("\\", "/"))
    return found


def read_results() -> dict:
    merged = {}
    for path in glob.glob(os.path.join(REPORTS, "results-*.json")):
        with open(path, encoding="utf-8") as handle:
            for node_id, entry in json.load(handle).items():
                for case_id in entry["tc"]:
                    merged.setdefault(case_id, []).append(entry["outcome"])
    summary = {}
    for case_id, outcomes in merged.items():
        for status in ("failed", "xpassed", "xfailed", "skipped", "passed"):
            if status in outcomes:
                summary[case_id] = status
                break
    return summary


def main() -> None:
    rows = read_specs()
    if not rows:
        sys.exit(f"No test cases found under {SPECS}")
    automation = find_automation()
    results = read_results()
    for row in rows:
        files = sorted(automation.get(row["id"], []))
        row["automated"] = "Yes" if files else "No"
        row["test_files"] = "\n".join(files)
        row["last_run"] = results.get(row["id"], "not run")

    os.makedirs(os.path.dirname(OUT_XLSX), exist_ok=True)
    columns = [
        ("id", "Test Case ID", 18),
        ("module", "Module", 22),
        ("feature", "Feature", 30),
        ("phase", "Type", 9),
        ("scenario", "Scenario / Steps", 70),
        ("expected", "Expected Result", 70),
        ("doc_status", "Doc Status", 22),
        ("automated", "Automated", 11),
        ("last_run", "Last Run", 12),
        ("test_files", "Automated Test File", 60),
    ]

    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    cases = wb.create_sheet("Test Cases")

    header_fill = PatternFill("solid", fgColor="1F3864")
    header_font = Font(bold=True, color="FFFFFF")
    for index, (_, title, width) in enumerate(columns, start=1):
        cell = cases.cell(row=1, column=index, value=title)
        cell.fill, cell.font = header_fill, header_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cases.column_dimensions[get_column_letter(index)].width = width
    run_fills = {
        "passed": "C6EFCE",
        "failed": "FFC7CE",
        "xfailed": "FFEB9C",
        "xpassed": "FFC7CE",
        "skipped": "D9D9D9",
    }
    for r, row in enumerate(rows, start=2):
        for c, (key, _, _) in enumerate(columns, start=1):
            cell = cases.cell(row=r, column=c, value=row[key])
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        fill = run_fills.get(row["last_run"])
        if fill:
            cases.cell(row=r, column=9).fill = PatternFill("solid", fgColor=fill)
    cases.freeze_panes = "B2"
    cases.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"

    summary.append(["COS360 test case catalog"])
    summary["A1"].font = Font(bold=True, size=14)
    summary.append([])
    summary.append(["Module", "Total", "Unit", "API", "UI", "Automated", "Passed", "Failed", "Known defect (xfail)", "Skipped", "Not run"])
    for cell in summary[3]:
        cell.fill, cell.font = header_fill, header_font
    by_module = defaultdict(list)
    for row in rows:
        by_module[row["module"]].append(row)
    totals = Counter()
    for module in MODULE_TITLES.values():
        items = by_module.get(module, [])
        if not items:
            continue
        phase = Counter(item["phase"] for item in items)
        run = Counter(item["last_run"] for item in items)
        line = [
            module,
            len(items),
            phase["Unit"],
            phase["API"],
            phase["UI"],
            sum(1 for item in items if item["automated"] == "Yes"),
            run["passed"],
            run["failed"] + run["xpassed"],
            run["xfailed"],
            run["skipped"],
            run["not run"],
        ]
        summary.append(line)
        for index, value in enumerate(line[1:], start=1):
            totals[index] += value
    summary.append(["TOTAL"] + [totals[i] for i in range(1, 11)])
    for cell in summary[summary.max_row]:
        cell.font = Font(bold=True)
    summary.column_dimensions["A"].width = 26
    for letter in "BCDEFGHIJK":
        summary.column_dimensions[letter].width = 14
    summary.append([])
    summary.append(["Test case types: Unit (backend, web, mobile unit tests), API (pytest against the QA tenant), UI (Playwright, web and mobile)."])
    summary.append(["Last Run comes from reports/results-*.json written by the most recent pytest run. UI results are not included yet."])

    wb.save(OUT_XLSX)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow([title for _, title, _ in columns])
        for row in rows:
            writer.writerow([row[key].replace("\n", "; ") for key, _, _ in columns])

    print(f"{len(rows)} test cases -> {os.path.relpath(OUT_XLSX, ROOT)} and {os.path.relpath(OUT_CSV, ROOT)}")
    print(f"automated: {sum(1 for r in rows if r['automated'] == 'Yes')}, with a last run result: {sum(1 for r in rows if r['last_run'] != 'not run')}")


if __name__ == "__main__":
    main()
