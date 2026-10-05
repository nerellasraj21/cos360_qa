import itertools
from decimal import Decimal

from api_tests.support import unique

Q4_DATES = ["2026-06-10", "2026-09-10", "2026-12-10", "2027-03-10"]
T3_DATES = ["2026-06-10", "2026-09-10", "2026-12-10"]

_phone_counter = itertools.count(1)


def D(value) -> Decimal:
    return Decimal(str(value))


def ok(response, *codes):
    expected = codes or (200, 201)
    assert response.status_code in expected, (
        f"{response.request.method} {response.request.url} -> {response.status_code} {response.text[:600]}"
    )
    return response


def detail_text(response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text
    detail = data.get("detail") if isinstance(data, dict) else data
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    if isinstance(data, dict) and detail is None:
        return str(data.get("message") or data)
    return str(detail)


def make_class(admin, cleanup, year_id, sections=("A",)):
    code = unique("fee_")
    response = ok(
        admin.post(
            "/masters/class_sections/",
            json={
                "name": code,
                "short_code": code[:10].upper(),
                "academic_year_id": year_id,
                "is_active": True,
                "sections": [{"name": f"{code}-{s}", "is_active": True} for s in sections],
            },
        )
    )
    data = response.json()
    cleanup.delete_later(admin, f"/masters/class_sections/{data['id']}")
    return {"id": data["id"], "name": data["name"], "sections": {s["name"]: s["id"] for s in data["sections"]}}


def make_term(admin, cleanup, year_id, dates=None, name=None, status="active"):
    dates = dates if dates is not None else Q4_DATES
    body = {
        "term_name": name or unique("fee_term_"),
        "term_status": status,
        "number_of_terms": len(dates),
        "academic_year_id": year_id,
        "fee_term_dates": [{"fee_term_date": d} for d in dates],
    }
    response = ok(admin.post("/fee/terms/", json=body))
    data = response.json()
    cleanup.delete_later(admin, f"/fee/terms/{data['id']}")
    return data


def make_category(admin, cleanup, year_id, name=None, status="active"):
    response = ok(
        admin.post(
            "/fee/categories/",
            json={"category_name": name or unique("fee_cat_"), "category_status": status, "academic_year_id": year_id},
        )
    )
    data = response.json()
    cleanup.delete_later(admin, f"/fee/categories/{data['id']}")
    return data


def make_type(admin, cleanup, year_id, category_id, term_id, name=None, status="active"):
    response = ok(
        admin.post(
            "/fee/types/",
            json={
                "type_name": name or unique("fee_type_"),
                "fee_category_id": category_id,
                "fee_term_id": term_id,
                "academic_year_id": year_id,
                "fee_status": status,
            },
        )
    )
    data = response.json()
    cleanup.delete_later(admin, f"/fee/types/{data['id']}")
    return data


def make_class_mapping(admin, cleanup, year_id, class_id, type_id, total="12000.00", mandatory=False):
    response = ok(
        admin.post(
            "/fee/class-mappings/",
            json={
                "class_id": class_id,
                "fee_type_id": type_id,
                "total_fee": str(total),
                "academic_year_id": year_id,
                "all_by_default": mandatory,
            },
        )
    )
    data = response.json()
    cleanup.delete_later(admin, f"/fee/class-mappings/{data['id']}")
    return data


def admission_body(year_id, cls, section_id, tag=None):
    tag = tag or unique("fee")
    n = next(_phone_counter)
    base = 7000000000 + (int(tag[-8:], 16) % 90000000) * 10 + n % 8
    return {
        "admission_number": tag.upper(),
        "admission_date": "2026-06-10",
        "admission_type": "regular",
        "academic_year_id": year_id,
        "admitted_academic_year_id": year_id,
        "admitted_class_id": cls["id"],
        "admitted_section_id": section_id,
        "current_class_id": cls["id"],
        "current_section_id": section_id,
        "address_line1": f"{tag} Fee Street",
        "address_line2": "Fee Lane",
        "city": f"Feecity{tag[-4:]}",
        "is_previous_school": False,
        "student": {
            "first_name": f"Fee{tag[-6:]}",
            "last_name": "Tester",
            "date_of_birth": "2018-03-04",
            "gender": "Male",
            "is_primary": "not_primary",
            "nationality": "Indian",
            "mother_tongue": "Telugu",
            "primary_phone": str(base),
            "father": {
                "name": f"Father {tag}",
                "email": f"{tag}.father@example.com",
                "phone": str(base),
                "occupation": "Engineer",
                "gender": "Male",
                "relation_to_student": "Father",
                "salary_range": "1l_3l",
            },
            "mother": {
                "name": f"Mother {tag}",
                "email": f"{tag}.mother@example.com",
                "phone": str(base + 1),
                "occupation": "Teacher",
                "gender": "Female",
                "relation_to_student": "Mother",
                "salary_range": "1l_3l",
            },
        },
    }


def make_student(admin, cleanup, year_id, cls, section_name=None, tag=None, sibling_of=None):
    section_id = cls["sections"][section_name] if section_name else next(iter(cls["sections"].values()))
    body = admission_body(year_id, cls, section_id, tag)
    if sibling_of:
        body["student"]["father"]["email"] = sibling_of["father_email"]
        body["student"]["mother"]["email"] = sibling_of["mother_email"]
        body["student"]["father"]["phone"] = sibling_of["father_phone"]
        body["student"]["mother"]["phone"] = str(int(sibling_of["father_phone"]) + 1)
        body["student"]["primary_phone"] = sibling_of["father_phone"]
    response = admin.post("/students/admission/", json=body)
    ok(response)
    data = response.json()
    student = {
        "id": data["student"]["id"],
        "admission_id": data["id"],
        "admission_number": data["admission_number"],
        "first_name": data["student"]["first_name"],
        "last_name": data["student"]["last_name"],
        "class_id": cls["id"],
        "section_id": section_id,
        "father_email": body["student"]["father"]["email"],
        "mother_email": body["student"]["mother"]["email"],
        "father_phone": body["student"]["father"]["phone"],
        "city": body["city"],
        "address_line1": body["address_line1"],
        "raw": data,
    }
    cleanup.delete_later(admin, f"/students/admission/{data['id']}")
    return student


def map_student(admin, cleanup, year_id, student, type_id, total="12000.00"):
    response = ok(
        admin.post(
            "/fee/student-mappings/",
            json={
                "student_id": student["id"],
                "student_admission_num": student["admission_number"],
                "class_id": student["class_id"],
                "section_id": student["section_id"],
                "fee_type_id": type_id,
                "total_fee": str(total),
                "academic_year_id": year_id,
            },
        )
    )
    data = response.json()
    cleanup.delete_later(admin, f"/fee/student-mappings/{data['id']}")
    return data


def pay(admin, student, year_id, amount, fee_items=None, method="cash", **extra):
    body = {
        "student_id": student["id"],
        "academic_year_id": year_id,
        "amount_to_pay": str(amount),
        "payment_method": method,
        "send_sms": False,
    }
    if fee_items is not None:
        body["fee_items"] = [{"fee_type_id": t, "amount": str(a)} for t, a in fee_items]
    body.update(extra)
    return admin.post("/fee/collection/pay", json=body)


def summary(admin, student, year_id, **params):
    params = {"academic_year_id": year_id, **params}
    return admin.get(f"/fee/collection/summary/{student['id']}", params=params)


def summary_item(admin, student, year_id, type_id, **params):
    data = ok(summary(admin, student, year_id, **params)).json()
    for item in data["items"]:
        if item["fee_type_id"] == type_id:
            return item
    raise AssertionError(f"fee type {type_id} not in summary {data}")
