import io
import random
import uuid

import openpyxl

from api_tests.support import QA_TENANT, Api, login, unique

TEMP_PASSWORD = "Welcome@123"
ALL_ROLES = ["admin", "staff", "teacher", "student", "parent"]


def phone_number() -> str:
    return "9" + "".join(random.choice("0123456789") for _ in range(9))


def email_address() -> str:
    return f"stf_{uuid.uuid4().hex[:10]}@qa.example"


def staff_payload(**overrides) -> dict:
    body = {"first_name": unique("stf_"), "phone": phone_number(), "address": "12 MG Road"}
    body.update(overrides)
    return body


def login_name(body: dict) -> str:
    return body.get("email") or body["phone"]


def granted(logins: dict, role: str, resource: str, action: str) -> bool:
    return action in (logins[role].get("permissions") or {}).get(resource, [])


def expected_status(logins: dict, role: str, resource: str, action: str, ok: int = 200) -> int:
    return ok if granted(logins, role, resource, action) else 403


def remove_staff(api: Api, staff: dict) -> None:
    api.delete(f"/staff/enrollment/{staff['id']}/photo")
    api.delete(f"/staff/enrollment/{staff['id']}")
    api.patch(f"/admin/users/{staff['user_id']}", json={"is_active": False})


def remove_staff_by_id(api: Api, staff_id: str) -> None:
    response = api.get(f"/staff/enrollment/{staff_id}")
    if response.status_code == 200:
        remove_staff(api, response.json())


def rand_past_date(low: int = 1990, high: int = 2012) -> str:
    year = random.randint(low, high)
    return f"{year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"


def make_workbook(rows: list, headers: list | None = None, sheet: str = "Staff Admission") -> bytes:
    workbook = openpyxl.Workbook()
    sheet_ref = workbook.active
    sheet_ref.title = sheet
    sheet_ref.append(
        headers
        or [
            "First Name",
            "Last Name",
            "Email",
            "Phone",
            "Address",
            "Designation",
            "Role",
            "Qualification Level",
            "Degree/Course",
            "Date of birth",
            "Gender",
        ]
    )
    for row in rows:
        sheet_ref.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def bulk_row(name, email="", phone=None, designation="", role="", level="", degree="", dob="", gender=""):
    return [name, "", email, phone if phone is not None else phone_number(), "addr", designation, role, level, degree, dob, gender]


def upload_workbook(api: Api, data: bytes, filename: str = "staff.xlsx"):
    return api.post(
        "/staff/enrollment/bulk-upload",
        files={"file": (filename, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def login_as(username: str, password: str = TEMP_PASSWORD) -> Api:
    data = login(username, password, QA_TENANT)
    client = Api(token=data["access_token"])
    client.login_data = data
    return client
