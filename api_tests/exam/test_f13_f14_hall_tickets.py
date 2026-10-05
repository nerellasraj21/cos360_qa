import io
import re
import zipfile

import pytest

from api_tests.exam.helpers import ALL_ROLES, OTHER_ROLES, audit_actions, create_exam, new_uuid, settings_lock
from api_tests.support import unique

DAYS = ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07", "2026-08-10", "2026-08-11", "2026-08-12"]
PATTERNS = {
    0: ["present"] * 8,
    1: ["present"] * 6 + ["absent"] * 2,
    2: ["present"] * 4 + ["late"] * 2 + ["absent"] * 2,
}
NEUTRAL = {"hall_ticket_min_attendance": 75, "grace_auto_apply": False, "reconduct_max_failed_subjects": 2}
D7 = "DEF-EXM-7: GET /exams/{id}/hall-tickets/download returns 400 DATABASE_ERROR for every eligible student; download-all swallows the same error and returns an empty ZIP"
TARGET_403 = "KG-3: Student and Parent hold exams:read and can reach this endpoint for any student"


@pytest.fixture(scope="module")
def attendance(admin, world):
    ids = []
    for idx, pattern in PATTERNS.items():
        for day, status in zip(DAYS, pattern):
            response = admin.post(
                "/student/attendance/", json={"student_id": world.students[idx]["id"], "date": day, "status": status, "remarks": None}
            )
            assert response.status_code in (200, 201), response.text
            ids.append(response.json()["id"])
    yield ids
    for aid in ids:
        try:
            admin.delete(f"/student/attendance/{aid}")
        except Exception:
            pass


@pytest.fixture
def settings(admin):
    with settings_lock():
        before = admin.get("/exam-settings")
        admin.put("/exam-settings", json={"hall_ticket_min_attendance": 75})
        yield lambda **kw: admin.put("/exam-settings", json={"hall_ticket_min_attendance": 75, **kw})
        if before.status_code == 200:
            data = before.json()
            data.pop("id", None)
            admin.put("/exam-settings", json=data)
        else:
            admin.put("/exam-settings", json=NEUTRAL)


@pytest.fixture
def hx(admin, world, cleanup, attendance, settings):
    exam_id = create_exam(admin, cleanup, world, dates=True, attendance_from_date=DAYS[0], attendance_to_date=DAYS[-1])
    return exam_id


def compute(admin, exam_id):
    response = admin.post(f"/exams/{exam_id}/hall-tickets/compute")
    assert response.status_code == 200, response.text
    return response.json()


def lists(admin, exam_id):
    eligible = admin.get(f"/exams/{exam_id}/hall-tickets/eligible").json()
    ineligible = admin.get(f"/exams/{exam_id}/hall-tickets/ineligible").json()
    return eligible, ineligible


def by_student(rows, student):
    return next(r for r in rows if r["student_id"] == student["id"])


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A01")
def test_compute_counts(admin, hx):
    body = compute(admin, hx)
    assert body == {"exam_id": hx, "total_students": 3, "eligible": 2, "ineligible": 1}


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A02")
def test_lists_have_documented_fields(admin, world, hx):
    compute(admin, hx)
    eligible, ineligible = lists(admin, hx)
    assert {r["student_id"] for r in eligible} == {world.students[0]["id"], world.students[1]["id"]}
    assert [r["student_id"] for r in ineligible] == [world.students[2]["id"]]
    for r in eligible + ineligible:
        for key in ("student_name", "admission_number", "attendance_percent", "attendance_ok", "fee_paid", "is_eligible", "ineligibility_reason"):
            assert key in r
    for r in eligible:
        assert r["is_eligible"] is True and r["ineligibility_reason"] is None
        assert re.fullmatch(r"HT-2025-\d{4}", r["hall_ticket_number"])
    s1 = by_student(eligible, world.students[0])
    s2 = by_student(eligible, world.students[1])
    assert float(s1["attendance_percent"]) == 100
    assert float(s2["attendance_percent"]) == 75
    s3 = ineligible[0]
    assert s3["hall_ticket_number"] is None and s3["ineligibility_reason"] == "LOW_ATTENDANCE"
    assert s3["attendance_ok"] is False and s3["fee_paid"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A03")
def test_compute_twice_no_duplicates(admin, hx):
    compute(admin, hx)
    second = compute(admin, hx)
    assert second["total_students"] == 3
    eligible, ineligible = lists(admin, hx)
    assert len(eligible) + len(ineligible) == 3


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A04")
def test_no_min_fee_means_fee_paid(admin, hx, settings):
    settings()
    compute(admin, hx)
    eligible, ineligible = lists(admin, hx)
    assert all(r["fee_paid"] is True for r in eligible + ineligible)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A04")
def test_min_fee_without_assigned_fee_fails_check(admin, world, hx, settings):
    settings(hall_ticket_min_fee_paid_pct=50)
    body = compute(admin, hx)
    assert body["eligible"] == 0 and body["ineligible"] == 3
    eligible, ineligible = lists(admin, hx)
    reasons = {r["student_id"]: r["ineligibility_reason"] for r in ineligible}
    assert reasons[world.students[0]["id"]] == "FEE_PENDING"
    assert reasons[world.students[1]["id"]] == "FEE_PENDING"
    assert reasons[world.students[2]["id"]] == "BOTH"
    assert all(r["fee_paid"] is False for r in ineligible)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A04")
def test_min_fee_zero_always_passes(admin, hx, settings):
    settings(hall_ticket_min_fee_paid_pct=0)
    body = compute(admin, hx)
    assert body["eligible"] == 2 and body["ineligible"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A05")
def test_exam_without_attendance_dates(admin, world, cleanup, attendance, settings):
    exam_id = create_exam(admin, cleanup, world)
    body = compute(admin, exam_id)
    assert body["eligible"] == 3 and body["ineligible"] == 0
    eligible, _ = lists(admin, exam_id)
    assert all(r["attendance_ok"] is True and r["attendance_percent"] is None for r in eligible)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A05")
def test_no_attendance_records_fails_check(admin, world, cleanup, attendance, settings):
    exam_id = create_exam(admin, cleanup, world, attendance_from_date="2026-07-01", attendance_to_date="2026-07-10")
    body = compute(admin, exam_id)
    assert body["eligible"] == 0 and body["ineligible"] == 3
    _, ineligible = lists(admin, exam_id)
    assert all(r["attendance_percent"] is None and r["attendance_ok"] is False for r in ineligible)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A06")
def test_compute_unknown_exam(admin):
    assert admin.post(f"/exams/{new_uuid()}/hall-tickets/compute").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A07")
def test_compute_on_draft_exam(admin, hx):
    assert admin.post(f"/exams/{hx}/deactivate").status_code == 200
    assert admin.post(f"/exams/{hx}/hall-tickets/compute").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A08")
def test_compute_writes_audit(admin, hx):
    compute(admin, hx)
    row = next(r for r in audit_actions(admin, hx) if r["action"] == "hall_tickets_computed")
    meta = row["metadata_"]
    assert meta["total_students"] == 3 and meta["eligible"] == 2 and meta["ineligible"] == 1


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A09")
def test_enrolled_students(admin, world, hx):
    response = admin.get(f"/exams/{hx}/hall-tickets/enrolled-students")
    assert response.status_code == 200
    rows = response.json()
    assert [r["student_id"] for r in rows] == [s["id"] for s in world.students]
    assert [r["student_name"] for r in rows] == sorted(r["student_name"] for r in rows)
    for r in rows:
        assert r["class_id"] == world.class_id and r["section_id"] == world.sections["a"]
        assert r["admission_number"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A10")
def test_override_attendance_makes_eligible(admin, world, hx):
    compute(admin, hx)
    s3 = world.students[2]
    response = admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_eligible"] is True and body["attendance_override"] is True
    assert body["attendance_ok"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A11")
def test_override_attendance_only_with_fee_failing(admin, world, hx, settings):
    settings(hall_ticket_min_fee_paid_pct=50)
    compute(admin, hx)
    s3 = world.students[2]
    response = admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    assert response.status_code == 200
    assert response.json()["is_eligible"] is False
    assert response.json()["ineligibility_reason"] == "FEE_PENDING"
    both = admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True, "fee_override": True})
    assert both.json()["is_eligible"] is True and both.json()["ineligibility_reason"] is None
    only_fee = admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"fee_override": True})
    assert only_fee.json()["ineligibility_reason"] == "LOW_ATTENDANCE"
    assert only_fee.json()["attendance_override"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A12")
def test_override_empty_body_resets(admin, world, hx):
    compute(admin, hx)
    s3 = world.students[2]
    admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    response = admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["attendance_override"] is False and body["fee_override"] is False
    assert body["is_eligible"] is False and body["ineligibility_reason"] == "LOW_ATTENDANCE"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A13")
def test_override_before_compute(admin, world, hx):
    response = admin.put(f"/exams/{hx}/hall-tickets/{world.students[2]['id']}/override", json={"attendance_override": True})
    assert response.status_code == 404
    assert response.json()["detail"] == "Eligibility record not found. Run compute first."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A14")
def test_override_survives_recompute(admin, world, hx):
    compute(admin, hx)
    s3 = world.students[2]
    admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    assert compute(admin, hx)["eligible"] == 3
    eligible, _ = lists(admin, hx)
    row = by_student(eligible, s3)
    assert row["is_eligible"] is True and row["attendance_override"] is True
    assert row["attendance_ok"] is False


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A15")
def test_override_writes_audit(admin, world, hx):
    compute(admin, hx)
    s3 = world.students[2]
    admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    row = next(r for r in audit_actions(admin, hx) if r["action"] == "eligibility_overridden")
    assert row["student_id"] == s3["id"]
    assert row["metadata_"]["final_eligible"] is True


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A16")
def test_override_does_not_assign_number_until_recompute(admin, world, hx):
    compute(admin, hx)
    s3 = world.students[2]
    admin.put(f"/exams/{hx}/hall-tickets/{s3['id']}/override", json={"attendance_override": True})
    eligible, _ = lists(admin, hx)
    assert by_student(eligible, s3)["hall_ticket_number"] is None
    compute(admin, hx)
    eligible, _ = lists(admin, hx)
    assert re.fullmatch(r"HT-2025-\d{4}", by_student(eligible, s3)["hall_ticket_number"])


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A17")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_compute_and_override_denied(role_clients, world, hx, role):
    client = role_clients[role]
    assert client.post(f"/exams/{hx}/hall-tickets/compute").status_code == 403
    assert client.put(f"/exams/{hx}/hall-tickets/{world.students[0]['id']}/override", json={}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A18")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_staff_roles_read_lists(role_clients, admin, hx, role):
    compute(admin, hx)
    for path in ("enrolled-students", "eligible", "ineligible"):
        assert role_clients[role].get(f"/exams/{hx}/hall-tickets/{path}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A18")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_parent_cannot_read_all_eligibility(role_clients, admin, hx, role):
    compute(admin, hx)
    assert role_clients[role].get(f"/exams/{hx}/hall-tickets/eligible").status_code == 403
    assert role_clients[role].get(f"/exams/{hx}/hall-tickets/ineligible").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A19")
def test_unauthenticated_eligibility(anon, world, hx):
    assert anon.post(f"/exams/{hx}/hall-tickets/compute").status_code == 401
    assert anon.get(f"/exams/{hx}/hall-tickets/eligible").status_code == 401
    assert anon.get(f"/exams/{hx}/hall-tickets/ineligible").status_code == 401
    assert anon.get(f"/exams/{hx}/hall-tickets/enrolled-students").status_code == 401
    assert anon.put(f"/exams/{hx}/hall-tickets/{world.students[0]['id']}/override", json={}).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A20")
def test_eligibility_tenant_isolation(admin, tenant_b, world, hx):
    compute(admin, hx)
    assert tenant_b.get(f"/exams/{hx}/hall-tickets/eligible").json() == []
    assert tenant_b.put(f"/exams/{hx}/hall-tickets/{world.students[2]['id']}/override", json={"attendance_override": True}).status_code == 404
    assert tenant_b.post(f"/exams/{hx}/hall-tickets/compute").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A21")
def test_compute_cschema_mismatch(foreign, hx):
    assert foreign.post(f"/exams/{hx}/hall-tickets/compute").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-13-A22")
def test_late_records_not_counted_as_present(admin, world, hx):
    compute(admin, hx)
    _, ineligible = lists(admin, hx)
    s3 = by_student(ineligible, world.students[2])
    assert float(s3["attendance_percent"]) == 50
    assert s3["ineligibility_reason"] == "LOW_ATTENDANCE"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A01")
def test_publish_hall_tickets(admin, hx):
    compute(admin, hx)
    response = admin.post(f"/exams/{hx}/hall-tickets/publish")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["exam_id"] == hx and body["hall_ticket_published"] is True and body["hall_ticket_published_at"]
    exam = admin.get(f"/exams/{hx}").json()
    assert exam["hall_ticket_published"] is True and exam["hall_ticket_published_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A02")
def test_publish_twice(admin, hx):
    first = admin.post(f"/exams/{hx}/hall-tickets/publish").json()
    second = admin.post(f"/exams/{hx}/hall-tickets/publish")
    assert second.status_code == 200
    assert second.json()["hall_ticket_published_at"] >= first["hall_ticket_published_at"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A03")
def test_publish_before_compute(admin, hx):
    assert admin.post(f"/exams/{hx}/hall-tickets/publish").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A04")
def test_publish_unknown_exam(admin):
    assert admin.post(f"/exams/{new_uuid()}/hall-tickets/publish").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A05")
def test_publish_writes_audit(admin, hx):
    admin.post(f"/exams/{hx}/hall-tickets/publish")
    assert "hall_tickets_published" in [r["action"] for r in audit_actions(admin, hx)]


def download(client, exam_id, student):
    return client.get(f"/exams/{exam_id}/hall-tickets/download", params={"student_id": student["id"]})


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A06")
def test_download_pdf_for_eligible_student(admin, world, hx):
    compute(admin, hx)
    s = world.students[0]
    response = download(admin, hx, s)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert f"hall-ticket-{s['id']}.pdf" in response.headers["content-disposition"]


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A07")
def test_download_ineligible_forbidden(admin, world, hx):
    compute(admin, hx)
    response = download(admin, hx, world.students[2])
    assert response.status_code == 403
    assert response.json()["detail"] == "Student is not eligible for a hall ticket."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A08")
def test_download_without_eligibility_row(admin, world, hx):
    response = download(admin, hx, world.students[0])
    assert response.status_code == 404
    assert response.json()["detail"] == "Hall ticket not found. Run compute first."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A09")
def test_download_requires_student_id(admin, hx):
    assert admin.get(f"/exams/{hx}/hall-tickets/download").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A10")
def test_pdf_contains_schedule(admin, world, hx):
    pypdf = pytest.importorskip("pypdf")
    compute(admin, hx)
    response = download(admin, hx, world.students[0])
    reader = pypdf.PdfReader(io.BytesIO(response.content))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "HALL TICKET" in text
    assert "01-02-2027" in text and "02-02-2027" in text and "03-02-2027" in text
    for key in ("math", "sci", "eng"):
        assert f"{world.tag}{key}" in text
    assert world.students[0]["admission_number"] in text


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A11")
def test_download_before_publish_allowed(admin, world, hx):
    compute(admin, hx)
    assert admin.get(f"/exams/{hx}").json()["hall_ticket_published"] is False
    assert download(admin, hx, world.students[1]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A12")
def test_download_all_zip(admin, world, hx):
    compute(admin, hx)
    response = admin.get(f"/exams/{hx}/hall-tickets/download-all")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    eligible, _ = lists(admin, hx)
    assert sorted(archive.namelist()) == sorted(f"hall-ticket-{r['hall_ticket_number']}.pdf" for r in eligible)
    assert len(archive.namelist()) == 2
    for name in archive.namelist():
        assert archive.read(name).startswith(b"%PDF")


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A13")
def test_download_all_without_eligible(admin, world, hx, settings):
    settings(hall_ticket_min_fee_paid_pct=50)
    compute(admin, hx)
    response = admin.get(f"/exams/{hx}/hall-tickets/download-all")
    assert response.status_code == 404
    assert response.json()["detail"] == "No eligible students found. Run compute first."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A14")
def test_student_cannot_download_other_students_ticket(admin, world, hx):
    compute(admin, hx)
    me = world.student_api(0)
    assert download(me, hx, world.students[1]).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A15")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_publish_denied(role_clients, hx, role):
    assert role_clients[role].post(f"/exams/{hx}/hall-tickets/publish").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A16")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_staff_roles_download_all(role_clients, admin, hx, role):
    compute(admin, hx)
    assert role_clients[role].get(f"/exams/{hx}/hall-tickets/download-all").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A16")
@pytest.mark.parametrize("role", ["admin", "teacher", "staff"])
def test_staff_roles_download(role_clients, admin, world, hx, role):
    compute(admin, hx)
    assert download(role_clients[role], hx, world.students[0]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A16")
@pytest.mark.parametrize("role", ["student", "parent"])
def test_student_parent_cannot_bulk_download(role_clients, admin, hx, role):
    compute(admin, hx)
    assert role_clients[role].get(f"/exams/{hx}/hall-tickets/download-all").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A17")
def test_download_unauthenticated(anon, world, hx):
    assert anon.post(f"/exams/{hx}/hall-tickets/publish").status_code == 401
    assert anon.get(f"/exams/{hx}/hall-tickets/download", params={"student_id": world.students[0]["id"]}).status_code == 401
    assert anon.get(f"/exams/{hx}/hall-tickets/download-all").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A18")
def test_download_tenant_isolation(admin, tenant_b, world, hx):
    compute(admin, hx)
    response = tenant_b.get(f"/exams/{hx}/hall-tickets/download", params={"student_id": world.students[0]["id"]})
    assert response.status_code == 404
    assert tenant_b.get(f"/exams/{hx}/hall-tickets/download-all").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-14-A19")
def test_publish_cschema_mismatch(foreign, hx):
    assert foreign.post(f"/exams/{hx}/hall-tickets/publish").status_code == 403
