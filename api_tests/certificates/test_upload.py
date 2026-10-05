import os
import re

import pytest

from api_tests.certificates import helpers as c
from api_tests.support import QA_TENANT, unique  # noqa: F401

FILE_KEY = r"^[0-9a-f-]{36}/%s/[0-9a-f-]{36}/[0-9a-f-]{36}\.%s$"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def post_both(client, student_id, type_id, **kwargs):
    return c.send_received(client, student_id, type_id, **kwargs), c.send_issued(
        client, student_id, type_id, c.iso(c.today()), **kwargs
    )


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A01")
def test_admin_uploads_received_document(admin, cfam, ctype, cleanup):
    body = c.received(admin, cleanup, cfam.s1.student_id, ctype["id"], remarks="original seen")
    assert set(body) == c.CERT_KEYS
    assert body["certificate_category"] == "received"
    assert body["issue_date"] is None
    assert body["type_name"] == ctype["name"]
    assert body["remarks"] == "original seen"
    assert re.match(FILE_KEY % ("received_docs", "pdf"), body["file_path"])
    assert body["file_path"].split("/")[1] == "received_docs"
    assert body["file_path"].split("/")[2] == cfam.s1.student_id
    assert os.path.exists(c.media_path(body["file_path"]))


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A02")
@pytest.mark.parametrize(
    "name,content,ctype_header,ext",
    [("c.png", c.PNG_BYTES, "image/png", "png"), ("c.docx", c.DOCX_BYTES, DOCX_TYPE, "docx"), ("c.jpg", c.JPG_BYTES, "image/jpeg", "jpg")],
)
def test_received_other_formats(admin, cfam, ctype, cleanup, name, content, ctype_header, ext):
    body = c.received(admin, cleanup, cfam.s1.student_id, ctype["id"], name=name, content=content, ctype=ctype_header)
    assert body["file_path"].endswith("." + ext)


FILE_REJECTIONS = [
    ({"name": "c.exe", "content": b"MZ", "ctype": "application/octet-stream"}, 400, "not allowed"),
    ({"name": "c.pdf", "content": b"not a pdf"}, 400, "corrupted"),
    ({"name": "c.pdf", "content": b""}, 400, "File is empty"),
    ({"name": "a/b.pdf"}, 400, "invalid characters"),
]


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A03")
@pytest.mark.tc("TC-CER-05-A03")
@pytest.mark.parametrize("kwargs,status,fragment", FILE_REJECTIONS)
def test_file_validation_matrix(admin, cfam, ctype, kwargs, status, fragment):
    for response in post_both(admin, cfam.s1.student_id, ctype["id"], **kwargs):
        assert response.status_code == status
        assert fragment in response.json()["detail"]


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A03")
@pytest.mark.tc("TC-CER-04-A04")
@pytest.mark.skip(reason="size boundaries need 10 MB and 11 MB files; the suite uses tiny files only")
def test_size_boundaries():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A05")
def test_unknown_student_and_type(admin, cfam, ctype):
    student = c.send_received(admin, c.UNKNOWN, ctype["id"])
    assert student.status_code == 404
    assert student.json()["detail"] == f"Student with id {c.UNKNOWN} not found"
    kind = c.send_received(admin, cfam.s1.student_id, c.UNKNOWN)
    assert kind.status_code == 404
    assert kind.json()["detail"] == f"Certificate type with id {c.UNKNOWN} not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A06")
def test_missing_form_fields(admin, cfam, ctype):
    base = {"student_id": cfam.s1.student_id, "certificate_type_id": ctype["id"]}
    for dropped in ("student_id", "certificate_type_id"):
        data = {k: v for k, v in base.items() if k != dropped}
        response = admin.post(f"{c.CERT}/received", data=data, files=c.file_part())
        assert response.status_code == 422
    assert admin.post(f"{c.CERT}/received", data=base).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A07")
@pytest.mark.tc("TC-CER-05-A03")
def test_remarks_length_limit(admin, cfam, ctype, cleanup):
    ok = c.received(admin, cleanup, cfam.s1.student_id, ctype["id"], remarks="r" * 255)
    assert len(ok["remarks"]) == 255
    for response in post_both(admin, cfam.s1.student_id, ctype["id"], remarks="r" * 256):
        assert response.status_code == 422
        assert response.json()["detail"] == "Remarks must be at most 255 characters"


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A08")
@pytest.mark.tc("TC-CER-05-A09")
@pytest.mark.skip(reason="blocked: no endpoint exposes file_audit_log and the suite may not read the database directly")
def test_upload_writes_audit_row():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A09")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_received_permission_matrix(role_clients, admin, cfam, ctype, cleanup, role, status):
    response = c.send_received(role_clients[role], cfam.s1.student_id, ctype["id"])
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{c.CERT}/{response.json()['id']}")
    elif role == "staff":
        assert response.json()["detail"] == "Only Admin can upload received documents"


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A10")
def test_received_requires_token(anon, cfam, ctype):
    assert c.send_received(anon, cfam.s1.student_id, ctype["id"]).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-04-A11")
@pytest.mark.tc("TC-CER-05-A11")
def test_upload_tenant_isolation(admin, tenant_b, tenant_b_name, cfam, ctype):
    assert c.send_received(tenant_b, cfam.s1.student_id, ctype["id"]).status_code == 404
    assert c.send_issued(tenant_b, cfam.s1.student_id, ctype["id"], c.iso(c.today())).status_code == 404
    mismatch = admin.post(
        f"{c.CERT}/received",
        data={"student_id": cfam.s1.student_id, "certificate_type_id": ctype["id"]},
        files=c.file_part(),
        headers={"cschema": tenant_b_name},
    )
    assert mismatch.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A01")
def test_admin_issues_certificate(admin, cfam, ctype, cleanup):
    body = c.issued(admin, cleanup, cfam.s1.student_id, ctype["id"], issue_date="2026-10-02")
    assert set(body) == c.CERT_KEYS
    assert body["certificate_category"] == "issued"
    assert body["issue_date"] == "2026-10-02"
    assert re.match(FILE_KEY % ("issued_certs", "pdf"), body["file_path"])
    assert os.path.exists(c.media_path(body["file_path"]))


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A02")
def test_issue_date_rules(admin, cfam, ctype, cleanup):
    assert c.send_issued(admin, cfam.s1.student_id, ctype["id"]).status_code == 422
    bad = c.send_issued(admin, cfam.s1.student_id, ctype["id"], "02-10-2026")
    assert bad.status_code == 422
    future = c.send_issued(admin, cfam.s1.student_id, ctype["id"], c.iso(c.today().replace(year=c.today().year + 1)))
    assert future.status_code == 201
    cleanup.delete_later(admin, f"{c.CERT}/{future.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A04")
def test_issue_unknown_references(admin, cfam, ctype):
    assert c.send_issued(admin, c.UNKNOWN, ctype["id"], c.iso(c.today())).status_code == 404
    assert c.send_issued(admin, cfam.s1.student_id, c.UNKNOWN, c.iso(c.today())).status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A05")
@pytest.mark.parametrize("role", ["admin", "staff"])
def test_legacy_create_is_received_category(role_clients, admin, cfam, ctype, cleanup, role):
    response = c.send_legacy(role_clients[role], cfam.s1.student_id, ctype["id"])
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{c.CERT}/{response.json()['id']}")
    body = response.json()
    assert body["certificate_category"] == "received"
    assert body["issue_date"] == c.iso(c.today())
    assert body["file_path"].split("/")[1] == "certificates"


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A06")
def test_legacy_create_wrong_field_name(admin, cfam, ctype):
    response = c.send_legacy(admin, cfam.s1.student_id, ctype["id"], field="certificate_file")
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A07")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 403), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_issued_permission_matrix(role_clients, admin, cfam, ctype, cleanup, role, status):
    response = c.send_issued(role_clients[role], cfam.s1.student_id, ctype["id"], c.iso(c.today()))
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{c.CERT}/{response.json()['id']}")
    elif role == "staff":
        assert response.json()["detail"] == "Only Admin can issue certificates"


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A08")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 201), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_legacy_permission_matrix(role_clients, admin, cfam, ctype, cleanup, role, status):
    response = c.send_legacy(role_clients[role], cfam.s1.student_id, ctype["id"])
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{c.CERT}/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-CER-05-A10")
def test_issue_requires_token(anon, cfam, ctype):
    assert c.send_issued(anon, cfam.s1.student_id, ctype["id"], c.iso(c.today())).status_code == 401
    assert c.send_legacy(anon, cfam.s1.student_id, ctype["id"]).status_code == 401
