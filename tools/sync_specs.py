import glob
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
source = os.path.join(app, "docs", "features")
testing = os.path.join(app, "docs", "testing")
if not os.path.isdir(source):
    raise SystemExit(f"Feature docs not found at {source}; set COS360_APP to the COS360_Full_App folder")

target = os.path.join(ROOT, "test_specs")
os.makedirs(target, exist_ok=True)
count = 0
for path in glob.glob(os.path.join(source, "*.md")):
    shutil.copy(path, target)
    count += 1
extras = {
    "e2e-journeys.md": "_journeys.md",
    "manual-testing-guide.md": "_manual-testing-guide.md",
    "strategy.md": "_strategy.md",
}
for name, copy_as in extras.items():
    path = os.path.join(testing, name)
    if os.path.isfile(path):
        shutil.copy(path, os.path.join(target, copy_as))
        count += 1
print(f"Copied {count} docs from {app} to test_specs/")
