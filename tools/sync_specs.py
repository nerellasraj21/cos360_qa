import glob
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = os.path.abspath(os.path.join(ROOT, os.environ.get("COS360_APP", "../COS360_Full_App")))
source = os.path.join(app, "docs", "features")
if not os.path.isdir(source):
    raise SystemExit(f"Feature docs not found at {source}; set COS360_APP to the COS360_Full_App folder")

target = os.path.join(ROOT, "test_specs")
os.makedirs(target, exist_ok=True)
count = 0
for path in glob.glob(os.path.join(source, "*.md")):
    shutil.copy(path, target)
    count += 1
print(f"Copied {count} feature docs from {source} to test_specs/")
