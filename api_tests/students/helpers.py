import io
import os
import random
import time
from datetime import date, timedelta

from api_tests.support import QA_TENANT, Api, unique

STUDENT_DEFAULT_PASSWORD = "student@123"
PARENT_DEFAULT_PASSWORD = "parent@123"
NEW_PASSWORD = "Qa-Changed-Pass-1"

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
JPG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
DOCX_BYTES = b"PK\x03\x04" + b"\x00" * 60

SELF_SERVICE_GRANTS = {
    "Student": [
        ("student_admissions", "read_own"),
        ("student_admissions", "list_own"),
        ("student_attendance", "read_own"),
        ("student_attendance", "list_own"),
        ("student_certificates", "read_own"),
        ("student_certificates", "list_own"),
        ("student_documents", "read_own"),
        ("student_documents", "list_own"),
        ("student_transport", "read_own"),
        ("profile", "read_own"),
        ("profile", "update_own"),
    ],
    "Parent": [
        ("student_admissions", "read_related"),
        ("student_admissions", "list_related"),
        ("student_attendance", "read_related"),
        ("student_attendance", "list_related"),
        ("student_certificates", "read_related"),
        ("student_certificates", "list_related"),
        ("student_documents", "read_related"),
        ("student_documents", "list_related"),
        ("student_transport", "read_related"),
    ],
}


def today() -> date:
    return date.today()


def iso(d: date) -> str:
    return d.isoformat()


def past_date(days: int = 30) -> str:
    return iso(today() - timedelta(days=days))


def future_date(days: int = 1) -> str:
    return iso(today() + timedelta(days=days))


def make_class(admin, year_id, cleanup, prefix="stu_", sections=("A", "B")):
    name = unique(prefix + "c")
    response = admin.post(
        "/masters/class_sections/",
        json={
            "name": name,
            "short_code": name[-6:],
            "academic_year_id": year_id,
            "sections": [{"name": s} for s in sections],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/class_sections/{data['id']}")
    return {
        "id": data["id"],
        "name": name,
        "sections": {s["name"]: s["id"] for s in data["sections"]},
    }


def admission_payload(year_id, klass, section="A", tag=None, **overrides):
    tag = tag or unique("stu_")
    body = {
        "admission_date": past_date(30),
        "admission_type": "regular",
        "academic_year_id": year_id,
        "admitted_class_id": klass["id"],
        "admitted_section_id": klass["sections"][section],
        "current_class_id": klass["id"],
        "current_section_id": klass["sections"][section],
        "address_line1": "12 Test Street",
        "student": {
            "first_name": f"{tag}fn",
            "last_name": f"{tag}ln",
            "date_of_birth": "2015-04-10",
            "gender": "M",
            "is_primary": "not_primary",
            "father": {
                "name": f"{tag} Father",
                "email": f"{tag}.father@example.com",
                "phone": "9876543210",
                "relation_to_student": "Father",
            },
            "mother": {
                "name": f"{tag} Mother",
                "email": f"{tag}.mother@example.com",
                "phone": "9876543211",
                "relation_to_student": "Mother",
            },
        },
    }
    for key, value in overrides.items():
        if key == "student":
            body["student"].update(value)
        else:
            body[key] = value
    body["_tag"] = tag
    return body


def post_admission(admin, body):
    payload = {k: v for k, v in body.items() if not k.startswith("_")}
    response = admin.post("/students/admission/", json=payload)
    for _ in range(25):
        if response.status_code < 400 or "_key" not in response.text:
            break
        if body.get("admission_number"):
            break
        time.sleep(random.uniform(0.2, 1.0))
        response = admin.post("/students/admission/", json=payload)
    return response


def create_admission(admin, year_id, klass, cleanup, section="A", tag=None, **overrides):
    body = admission_payload(year_id, klass, section, tag, **overrides)
    response = post_admission(admin, body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/students/admission/{data['id']}")
    return Admission(data, body)


class Admission:
    def __init__(self, data, body):
        self.data = data
        self.body = body
        self.admission_id = data["id"]
        self.student_id = data["student"]["id"]
        self.number = data["admission_number"]
        self.tag = body["_tag"]
        self.father_email = body["student"]["father"].get("email")
        self.mother_email = body["student"]["mother"].get("email")
        self.first_name = body["student"]["first_name"]


def set_first_password(tenant, username, password, new_password=NEW_PASSWORD, year_id=None):
    anon = Api(tenant_header=tenant)
    try:
        if year_id is None:
            year_id = anon.get("/auth/academic-years").json()[0]["id"]
        response = anon.post("/auth/login", json={"username": username, "password": password, "academic_year_id": year_id})
        assert response.status_code == 200, response.text
        data = response.json()
        if data.get("requires_password_change"):
            done = anon.post(
                "/auth/staff/set-password",
                json={
                    "change_password_token": data["change_password_token"],
                    "new_password": new_password,
                    "confirm_password": new_password,
                },
            )
            assert done.status_code == 200, done.text
            data = done.json()
        return data
    finally:
        anon.close()


def client_for(admission_number_or_email, default_password, cleanup, year_id=None):
    data = set_first_password(QA_TENANT, admission_number_or_email, default_password, year_id=year_id)
    api = Api(token=data["access_token"])
    cleanup.add(api.close)
    api.login_data = data
    return api


def student_client(adm, cleanup, year_id=None):
    return client_for(adm.number, STUDENT_DEFAULT_PASSWORD, cleanup, year_id)


def parent_client(email, cleanup, year_id=None):
    return client_for(email, PARENT_DEFAULT_PASSWORD, cleanup, year_id)


def apply_self_service_grants(admin, roles=("Student", "Parent"), only=None):
    listing = admin.get("/admin/role-mgmt/roles/")
    assert listing.status_code == 200, listing.text
    body = listing.json()
    role_rows = body.get("roles", body) if isinstance(body, dict) else body
    ids = {r["name"]: r["id"] for r in role_rows}
    added = []
    for role in roles:
        current = admin.get(f"/admin/role-mgmt/roles/{ids[role]}/permissions").json()["permissions"]
        for resource, action in SELF_SERVICE_GRANTS[role]:
            if only and resource not in only:
                continue
            have = {(a["action"]): a["is_granted"] for a in current.get(resource, [])}
            if have.get(action) is True:
                continue
            response = admin.put(
                f"/admin/role-mgmt/roles/{ids[role]}/permissions",
                params={"resource": resource, "action": action, "is_granted": "true"},
            )
            assert response.status_code == 200, response.text
            added.append((ids[role], resource, action, have.get(action)))
    return added


KEEP_GRANTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".keep_grants")


def revert_self_service_grants(admin, added):
    if os.path.exists(KEEP_GRANTS_FILE):
        return
    for role_id, resource, action, previous in added:
        admin.put(
            f"/admin/role-mgmt/roles/{role_id}/permissions",
            params={"resource": resource, "action": action, "is_granted": "true" if previous else "false"},
        )


def upload_file(name, content, content_type):
    return {"file": (name, io.BytesIO(content), content_type)}


BULK_HEADERS = [
    "Admission no",
    "Admission date",
    "First name",
    "last name",
    "Date of birth (DD-MM-YYYY)",
    "Gender",
    "Student type",
    "Aadhar No",
    "Apaar no",
    "joining class",
    "joining section",
    "Father name",
    "Father Email",
    "Father phone",
    "Mother Name",
    "Mother Email",
    "Mother Phone",
    "Address Line 1",
]


def build_workbook(rows, headers=None, sheet="Student Admission"):
    import openpyxl

    headers = headers or BULK_HEADERS
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for row in rows:
        ws.append([row.get(name) for name in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def bulk_row(klass, tag=None, **overrides):
    tag = tag or unique("stu_b")
    row = {
        "First name": f"{tag}fn",
        "last name": f"{tag}ln",
        "Date of birth (DD-MM-YYYY)": "10-04-2015",
        "Gender": "M",
        "joining class": klass["name"],
        "joining section": None,
        "Father name": f"{tag} Father",
        "Father Email": f"{tag}.father@example.com",
        "Father phone": "9876543210",
        "Mother Name": f"{tag} Mother",
        "Mother Email": f"{tag}.mother@example.com",
        "Mother Phone": "9876543211",
        "Address Line 1": "5 Bulk Street",
    }
    row.update(overrides)
    return row


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
