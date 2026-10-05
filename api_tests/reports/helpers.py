import uuid
from datetime import date

from api_tests.support import QA_B_TENANT, Api, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]


def other_tenant_header(client):
    return Api(token=client.token, tenant_header=QA_B_TENANT)


def fresh_year():
    return 2100 + int(uuid.uuid4().hex[:6], 16) % 6900


def make_class(admin, cleanup, academic_year_id, sections=("A",)):
    token = unique("rpt_")
    response = admin.post(
        "/masters/class_sections/",
        json={
            "name": token,
            "academic_year_id": academic_year_id,
            "short_code": token[:8],
            "sections": [{"name": name} for name in sections],
        },
    )
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/class_sections/{data['id']}")
    return data


def _drop_admission(admin, admission_id):
    admin.delete(f"/students/admission/{admission_id}")


def admission_body(academic_year_id, class_id, section_id, token, city="Hyderabad", **over):
    body = {
        "admission_date": "2026-06-10",
        "admission_number": token,
        "admission_type": "regular",
        "academic_year_id": academic_year_id,
        "admitted_academic_year_id": academic_year_id,
        "admitted_class_id": class_id,
        "admitted_section_id": section_id,
        "current_class_id": class_id,
        "current_section_id": section_id,
        "address_line1": f"{token} Street",
        "city": city,
        "is_previous_school": False,
        "student": {
            "first_name": token,
            "last_name": "Qa",
            "date_of_birth": "2018-05-05",
            "gender": "Male",
            "is_primary": "not_primary",
            "nationality": "Indian",
            "mother_tongue": "Telugu",
            "primary_phone": "9000100001",
            "father": {
                "name": f"Dad {token}",
                "email": f"{token}.dad@example.com",
                "phone": "9000100002",
                "occupation": "Clerk",
                "gender": "Male",
                "relation_to_student": "Father",
                "salary_range": "1l_3l",
            },
            "mother": {
                "name": f"Mom {token}",
                "email": f"{token}.mom@example.com",
                "phone": "9000100003",
                "occupation": "Nurse",
                "gender": "Female",
                "relation_to_student": "Mother",
                "salary_range": "1l_3l",
            },
        },
    }
    body.update(over)
    return body


def make_student(admin, cleanup, academic_year_id, class_data, section_index=0, city="Hyderabad", **over):
    token = unique("rpt_s")
    section_id = class_data["sections"][section_index]["id"]
    body = admission_body(academic_year_id, class_data["id"], section_id, token, city, **over)
    response = admin.post("/students/admission/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.add(_drop_admission, admin, data["id"])
    return {
        "student_id": data["student"]["id"],
        "admission_id": data["id"],
        "admission_number": data["admission_number"],
        "class_id": class_data["id"],
        "section_id": section_id,
        "city": city,
    }


def mark_attendance(admin, cleanup, student_id, day, status):
    response = admin.post(
        "/student/attendance/", json={"student_id": student_id, "date": day, "status": status, "remarks": None}
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    if data.get("id"):
        cleanup.delete_later(admin, f"/student/attendance/{data['id']}")
    return data


def today():
    return date.today().isoformat()


def make_designation(admin, cleanup):
    response = admin.post("/staff/designations/", json={"title": unique("rpt_des_")})
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/staff/designations/{data['id']}")
    return data


def make_staff(admin, cleanup, designation_id, gender="Female", **over):
    token = unique("rpt_st")
    body = {
        "first_name": token,
        "last_name": "Qa",
        "email": f"{token}@example.com",
        "phone": "9000" + str(int(uuid.uuid4().hex[:7], 16) % 10**7).zfill(7),
        "address": f"{token} Street",
        "gender": gender,
        "designation_id": designation_id,
        "department": "Admin",
        "joining_date": "2026-01-05",
    }
    body.update(over)
    response = admin.post("/staff/enrollment", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/staff/enrollment/{data['id']}")
    return data


def mark_staff_attendance(admin, cleanup, staff_id, day, status):
    response = admin.post("/staff/attendance", json={"staff_id": staff_id, "date": day, "status": status})
    assert response.status_code in (200, 201), response.text
    data = response.json()
    cleanup.delete_later(admin, f"/staff/attendance/{data['id']}")
    return data
