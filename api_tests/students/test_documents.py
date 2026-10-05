import io
import os
import re

import pytest

from api_tests.students import helpers as h
from api_tests.support import BACKEND_ROOT, unique

UNKNOWN = "00000000-0000-0000-0000-000000000001"
BASE = "/students/documents"
PATH_PATTERN = re.compile(r"^student_documents[\\/][0-9a-f-]{36}\.\w+$")
DOC_KEYS = {"id", "student_id", "document_type", "file_path", "upload_date"}
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def send(client, student_id, doc_type, name="d.pdf", content=h.PDF_BYTES, ctype="application/pdf"):
    return client.post(
        f"{BASE}/",
        data={"student_id": student_id, "document_type": doc_type},
        files={"document_file": (name, io.BytesIO(content), ctype)},
    )


def stored(admin, cleanup, student_id, doc_type=None, **kwargs):
    response = send(admin, student_id, doc_type or unique("stu_dt"), **kwargs)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
    return response.json()


def on_disk(file_path):
    return os.path.exists(os.path.join(BACKEND_ROOT, file_path))


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A01")
def test_upload_pdf(admin, family, cleanup):
    response = send(admin, family.c1.student_id, "Birth Certificate")
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")
    body = response.json()
    assert set(body) == DOC_KEYS
    assert body["student_id"] == family.c1.student_id
    assert body["document_type"] == "Birth Certificate"
    assert PATH_PATTERN.match(body["file_path"])
    assert body["file_path"].endswith(".pdf")
    assert on_disk(body["file_path"])


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A02")
@pytest.mark.parametrize(
    "name,content,ctype",
    [("d.jpg", h.JPG_BYTES, "image/jpeg"), ("d.png", h.PNG_BYTES, "image/png"), ("d.docx", h.DOCX_BYTES, DOCX_TYPE)],
)
def test_upload_other_formats(admin, family, cleanup, name, content, ctype):
    body = stored(admin, cleanup, family.c1.student_id, name=name, content=content, ctype=ctype)
    assert body["file_path"].endswith(os.path.splitext(name)[1])


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A03")
@pytest.mark.parametrize(
    "name,content,ctype,message",
    [
        ("d.doc", b"abc", "application/msword", "Invalid file extension"),
        ("d.txt", b"abc", "text/plain", "Invalid file extension"),
        ("d.pdf", b"hello", "application/pdf", "Invalid PDF file format"),
        ("d.pdf", b"", "application/pdf", "Empty file not allowed"),
    ],
)
def test_upload_rejections(admin, family, name, content, ctype, message):
    response = send(admin, family.c1.student_id, unique("stu_dt"), name=name, content=content, ctype=ctype)
    assert response.status_code == 400
    assert message in response.json()["detail"]["message"]


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A03")
@pytest.mark.skip(reason="size boundary needs a 5 MB file; the suite uses tiny files only")
def test_upload_size_boundary():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A04")
def test_duplicate_type_per_student(admin, family, cleanup):
    doc_type = unique("stu_dup")
    stored(admin, cleanup, family.c1.student_id, doc_type)
    again = send(admin, family.c1.student_id, doc_type)
    assert again.status_code == 422
    assert "already exists for this student" in again.json()["detail"]["message"]
    stored(admin, cleanup, family.other.student_id, doc_type)


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A05")
def test_missing_or_blank_fields(admin, family):
    no_type = admin.post(
        f"{BASE}/",
        data={"student_id": family.c1.student_id},
        files={"document_file": ("d.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    assert no_type.status_code == 422
    blank = send(admin, family.c1.student_id, "   ")
    assert blank.status_code == 400
    assert blank.json()["detail"]["message"] == "Document type is required"
    no_file = admin.post(f"{BASE}/", data={"student_id": family.c1.student_id, "document_type": "x"})
    assert no_file.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A06")
def test_upload_for_unknown_student(admin):
    response = send(admin, UNKNOWN, unique("stu_dt"))
    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Student not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A07")
def test_patch_replaces_file_and_type(admin, family, cleanup):
    created = stored(admin, cleanup, family.c1.student_id)
    new_type = unique("stu_nt")
    response = admin.patch(
        f"{BASE}/{created['id']}",
        data={"document_type": new_type},
        files={"document_file": ("n.png", io.BytesIO(h.PNG_BYTES), "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == created["id"]
    assert body["document_type"] == new_type
    assert body["file_path"] != created["file_path"]
    assert on_disk(body["file_path"])
    assert not on_disk(created["file_path"])


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A08")
def test_patch_unknown_document(admin):
    response = admin.patch(
        f"{BASE}/{UNKNOWN}",
        data={"document_type": "x"},
        files={"document_file": ("n.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Document not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A09")
@pytest.mark.parametrize(
    "role,status", [("admin", 201), ("staff", 201), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_upload_permission_matrix(role_clients, admin, family, cleanup, role, status):
    response = send(role_clients[role], family.c1.student_id, unique("stu_dt"))
    assert response.status_code == status
    if status == 201:
        cleanup.delete_later(admin, f"{BASE}/{response.json()['id']}")


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A10")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_patch_permission_matrix(role_clients, admin, family, cleanup, role, status):
    created = stored(admin, cleanup, family.c1.student_id)
    response = role_clients[role].patch(
        f"{BASE}/{created['id']}",
        data={"document_type": unique("stu_pt")},
        files={"document_file": ("n.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A11")
def test_upload_and_patch_require_token(anon, family):
    assert send(anon, family.c1.student_id, "x").status_code == 401
    response = anon.patch(
        f"{BASE}/{UNKNOWN}",
        data={"document_type": "x"},
        files={"document_file": ("n.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    assert response.status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-14-A12")
def test_upload_tenant_isolation(admin, tenant_b, tenant_b_name, family):
    assert send(tenant_b, family.c1.student_id, unique("stu_dt")).status_code == 404
    mismatch = admin.post(
        f"{BASE}/",
        data={"student_id": family.c1.student_id, "document_type": unique("stu_dt")},
        files={"document_file": ("d.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
        headers={"cschema": tenant_b_name},
    )
    assert mismatch.status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A01")
def test_list_documents(admin, family, cleanup):
    first = stored(admin, cleanup, family.c2.student_id)
    second = stored(admin, cleanup, family.c2.student_id)
    response = admin.get(f"{BASE}/", params={"student_id": family.c2.student_id})
    assert response.status_code == 200
    assert {d["id"] for d in response.json()} == {first["id"], second["id"]}
    assert all(set(d) == DOC_KEYS for d in response.json())


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A02")
def test_list_argument_errors(admin):
    assert admin.get(f"{BASE}/").status_code == 422
    assert admin.get(f"{BASE}/", params={"student_id": UNKNOWN}).status_code == 404
    assert admin.get(f"{BASE}/", params={"student_id": "abc"}).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A03")
def test_unified_documents_include_certificates(admin, family, cleanup):
    student_id = family.c1.student_id
    doc = stored(admin, cleanup, student_id)
    created_type = admin.post("/certificates/types/", json={"name": unique("stu_ct"), "description": "d"})
    assert created_type.status_code == 201, created_type.text
    type_id = created_type.json()["id"]
    received = admin.post(
        "/certificates/received",
        data={"student_id": student_id, "certificate_type_id": type_id},
        files={"file": ("c.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    issued = admin.post(
        "/certificates/issued",
        data={"student_id": student_id, "certificate_type_id": type_id, "issue_date": h.iso(h.today())},
        files={"file": ("i.pdf", io.BytesIO(h.PDF_BYTES), "application/pdf")},
    )
    assert received.status_code == 201 and issued.status_code == 201
    cleanup.delete_later(admin, f"/certificates/types/{type_id}")
    cleanup.delete_later(admin, f"/certificates/{received.json()['id']}")
    cleanup.delete_later(admin, f"/certificates/{issued.json()['id']}")
    response = admin.get(f"{BASE}/all", params={"student_id": student_id})
    assert response.status_code == 200
    mine = {i["id"]: i for i in response.json()}
    assert mine[doc["id"]]["source"] == "document"
    assert mine[received.json()["id"]]["source"] == "certificate"
    assert mine[issued.json()["id"]]["source"] == "certificate"
    assert mine[received.json()["id"]]["type_name"] == created_type.json()["name"]
    assert mine[received.json()["id"]]["certificate_category"] == "received"
    assert mine[issued.json()["id"]]["certificate_category"] == "issued"
    stamps = [i["upload_date"] for i in response.json()]
    assert stamps == sorted(stamps, reverse=True)


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A03")
@pytest.mark.skip(reason="blocked: the receipt source needs a fee payment, which belongs to FEE fixtures")
def test_unified_documents_include_receipts():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A04")
def test_get_single_document(admin, family, cleanup):
    created = stored(admin, cleanup, family.c1.student_id)
    ok = admin.get(f"{BASE}/{created['id']}")
    assert ok.status_code == 200
    assert ok.json() == created
    missing = admin.get(f"{BASE}/{UNKNOWN}")
    assert missing.status_code == 404
    assert missing.json()["detail"]["message"] == "Document not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A05")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_read_permission_matrix(role_clients, admin, family, cleanup, role, status):
    created = stored(admin, cleanup, family.c1.student_id)
    client = role_clients[role]
    assert client.get(f"{BASE}/", params={"student_id": family.c1.student_id}).status_code == status
    assert client.get(f"{BASE}/all", params={"student_id": family.c1.student_id}).status_code == status
    assert client.get(f"{BASE}/{created['id']}").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A06")
def test_teacher_reads_any_students_documents(teacher, family):
    assert teacher.get(f"{BASE}/", params={"student_id": family.other.student_id}).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A07")
def test_reads_require_token(anon, family):
    for path in (f"{BASE}/?student_id={family.c1.student_id}", f"{BASE}/all?student_id={family.c1.student_id}", f"{BASE}/{UNKNOWN}"):
        assert anon.get(path).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-15-A08")
def test_reads_tenant_isolation(admin, tenant_b, tenant_b_name, family):
    assert tenant_b.get(f"{BASE}/", params={"student_id": family.c1.student_id}).status_code == 404
    assert tenant_b.get(f"{BASE}/all", params={"student_id": family.c1.student_id}).status_code == 404
    header = {"cschema": tenant_b_name}
    assert admin.get(f"{BASE}/", params={"student_id": family.c1.student_id}, headers=header).status_code == 403
    assert admin.get(f"{BASE}/{UNKNOWN}", headers=header).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A01")
def test_delete_document_removes_row_and_file(admin, family):
    response = send(admin, family.c1.student_id, unique("stu_dt"))
    created = response.json()
    assert on_disk(created["file_path"])
    deleted = admin.delete(f"{BASE}/{created['id']}")
    assert deleted.status_code == 204
    ids = [d["id"] for d in admin.get(f"{BASE}/", params={"student_id": family.c1.student_id}).json()]
    assert created["id"] not in ids
    assert not on_disk(created["file_path"])


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A02")
def test_delete_unknown_document(admin):
    response = admin.delete(f"{BASE}/{UNKNOWN}")
    assert response.status_code == 404
    assert response.json()["detail"]["message"] == "Document not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A03")
def test_delete_permission_matrix(role_clients, admin, family):
    created = send(admin, family.c1.student_id, unique("stu_dt")).json()
    for role in ("staff", "teacher", "student", "parent"):
        assert role_clients[role].delete(f"{BASE}/{created['id']}").status_code == 403
    assert admin.get(f"{BASE}/{created['id']}").status_code == 200
    assert admin.delete(f"{BASE}/{created['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A04")
def test_documented_missing_endpoints(admin, family, cleanup):
    created = stored(admin, cleanup, family.c1.student_id)
    assert admin.get(f"{BASE}/{created['id']}/download").status_code == 404
    assert admin.post(f"{BASE}/{created['id']}/verify").status_code == 404
    assert admin.get("/students/document-types/").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A05")
def test_delete_requires_token(anon):
    assert anon.delete(f"{BASE}/{UNKNOWN}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-16-A06")
def test_delete_tenant_isolation(admin, tenant_b, tenant_b_name, family, cleanup):
    created = stored(admin, cleanup, family.c1.student_id)
    assert tenant_b.delete(f"{BASE}/{created['id']}").status_code == 404
    assert admin.delete(f"{BASE}/{created['id']}", headers={"cschema": tenant_b_name}).status_code == 403
    assert admin.get(f"{BASE}/{created['id']}").status_code == 200
