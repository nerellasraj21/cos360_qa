import json, sys
from openpyxl import Workbook

out, rows = sys.argv[1], json.loads(sys.argv[2])
wb = Workbook()
ws = wb.active
ws.title = "Student Admission"
headers = ["First name", "joining class", "joining section", "Father name", "Father phone", "Address Line 1"]
ws.append(headers)
for r in rows:
    ws.append([r.get(h, "") for h in headers])
wb.save(out)
