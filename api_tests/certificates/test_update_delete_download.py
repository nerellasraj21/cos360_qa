import os
import time

import httpx
import pytest

from api_tests.certificates import helpers as c


def patch(client, certificate_id, files=None, **data):
    return client.patch(f"{c.CERT}/{certificate_id}", data=data or None, files=files)


@pytest.fixture
def cert(admin, cfam, ctype, cleanup):
    return c.received(admin, cleanup, cfam.s1.student_id, ctype["id"], remarks="before")


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A01")
def test_patch_remarks_and_issue_date(admin, cert):
    time.sleep(0.05)
    response = patch(admin, cert["id"], remarks="after", issue_date="2026-01-15")
    assert response.status_code == 200
    body = response.json()
    assert body["remarks"] == "after" and body["issue_date"] == "2026-01-15"
    assert body["file_path"] == cert["file_path"]
    assert body["updated_at"] >= cert["updated_at"]


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A02")
def test_patch_with_new_file_moves_old_to_stale(admin, cert):
    old_path = c.media_path(cert["file_path"])
    assert os.path.exists(old_path)
    response = patch(admin, cert["id"], files=c.file_part("n.png", c.PNG_BYTES, "image/png"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_path"] != cert["file_path"]
    assert body["file_path"].split("/")[1] == "certificates"
    assert body["file_path"].endswith(".png")
    assert os.path.exists(c.media_path(body["file_path"]))
    assert not os.path.exists(old_path)
    assert os.path.exists(c.stale_path(cert["file_path"]))


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A02")
@pytest.mark.skip(reason="blocked: the stale registry row and the audit row are not exposed by any endpoint")
def test_patch_writes_registry_and_audit_rows():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A03")
@pytest.mark.parametrize(
    "kwargs,fragment",
    [
        ({"name": "x.exe", "content": b"MZ", "ctype": "application/octet-stream"}, "not allowed"),
        ({"name": "x.pdf", "content": b"fake"}, "corrupted"),
    ],
)
def test_patch_with_invalid_file_changes_nothing(admin, cert, kwargs, fragment):
    response = patch(admin, cert["id"], files=c.file_part(**kwargs))
    assert response.status_code == 400
    assert fragment in response.json()["detail"]
    unchanged = admin.get(f"{c.CERT}/{cert['id']}").json()
    assert unchanged["file_path"] == cert["file_path"]
    assert os.path.exists(c.media_path(cert["file_path"]))


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A04")
def test_patch_with_unknown_type(admin, cert):
    response = patch(admin, cert["id"], certificate_type_id=c.UNKNOWN)
    assert response.status_code == 404
    assert response.json()["detail"] == f"Certificate type with id {c.UNKNOWN} not found"
    assert admin.get(f"{c.CERT}/{cert['id']}").json()["certificate_type_id"] == cert["certificate_type_id"]


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A05")
def test_patch_unknown_certificate(admin):
    response = patch(admin, c.UNKNOWN, remarks="x")
    assert response.status_code == 404
    assert response.json()["detail"] == f"Certificate with id {c.UNKNOWN} not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A06")
def test_patch_without_fields(admin, cert):
    response = admin.patch(f"{c.CERT}/{cert['id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["remarks"] == cert["remarks"] and body["file_path"] == cert["file_path"]


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A07")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_patch_permission_matrix(role_clients, cert, role, status):
    assert patch(role_clients[role], cert["id"], remarks=f"by {role}").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A08")
def test_patch_requires_token(anon, cert):
    assert patch(anon, cert["id"], remarks="x").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-08-A09")
def test_patch_tenant_isolation(admin, tenant_b, tenant_b_name, cert):
    assert patch(tenant_b, cert["id"], remarks="x").status_code == 404
    mismatch = admin.patch(f"{c.CERT}/{cert['id']}", data={"remarks": "x"}, headers={"cschema": tenant_b_name})
    assert mismatch.status_code == 403
    assert admin.get(f"{c.CERT}/{cert['id']}").json()["remarks"] == "before"


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A01")
def test_delete_moves_file_to_stale(admin, cfam, ctype):
    created = c.send_received(admin, cfam.s1.student_id, ctype["id"]).json()
    live = c.media_path(created["file_path"])
    assert os.path.exists(live)
    assert admin.delete(f"{c.CERT}/{created['id']}").status_code == 204
    assert admin.get(f"{c.CERT}/{created['id']}").status_code == 404
    assert not os.path.exists(live)
    assert os.path.exists(c.stale_path(created["file_path"]))


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A01")
@pytest.mark.tc("TC-CER-14-A01")
@pytest.mark.skip(reason="blocked: the stale registry rows and the file audit log are not exposed by any endpoint")
def test_delete_writes_registry_and_audit_rows():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A02")
def test_delete_twice(admin, cfam, ctype):
    created = c.send_received(admin, cfam.s1.student_id, ctype["id"]).json()
    assert admin.delete(f"{c.CERT}/{created['id']}").status_code == 204
    again = admin.delete(f"{c.CERT}/{created['id']}")
    assert again.status_code == 404
    assert again.json()["detail"] == f"Certificate with id {created['id']} not found"


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A03")
def test_delete_when_file_is_already_missing(admin, cfam, ctype):
    created = c.send_received(admin, cfam.s1.student_id, ctype["id"]).json()
    os.remove(c.media_path(created["file_path"]))
    assert admin.delete(f"{c.CERT}/{created['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A04")
def test_deleted_certificate_disappears_everywhere(admin, cfam, ctype):
    created = c.send_received(admin, cfam.s1.student_id, ctype["id"]).json()
    assert admin.delete(f"{c.CERT}/{created['id']}").status_code == 204
    mine = cfam.s1_client.get(f"{c.CERT}/my").json()
    assert created["id"] not in [i["id"] for i in mine["items"]]
    child = cfam.p1_client.get(f"{c.CERT}/my-child/{cfam.s1.student_id}").json()
    assert created["id"] not in [i["id"] for i in child["items"]]
    docs = admin.get("/students/documents/all", params={"student_id": cfam.s1.student_id}).json()
    assert created["id"] not in [d["id"] for d in docs]


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A06")
def test_delete_permission_matrix(role_clients, admin, cfam, ctype):
    created = c.send_received(admin, cfam.s1.student_id, ctype["id"]).json()
    for role in ("staff", "teacher", "student", "parent"):
        assert role_clients[role].delete(f"{c.CERT}/{created['id']}").status_code == 403
    assert admin.get(f"{c.CERT}/{created['id']}").status_code == 200
    assert admin.delete(f"{c.CERT}/{created['id']}").status_code == 204


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A07")
def test_delete_requires_token(anon, cert):
    assert anon.delete(f"{c.CERT}/{cert['id']}").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-09-A08")
def test_delete_tenant_isolation(admin, tenant_b, tenant_b_name, cert):
    assert tenant_b.delete(f"{c.CERT}/{cert['id']}").status_code == 404
    assert admin.delete(f"{c.CERT}/{cert['id']}", headers={"cschema": tenant_b_name}).status_code == 403
    assert admin.get(f"{c.CERT}/{cert['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A01")
def test_admin_download_link(admin, cert):
    response = admin.get(f"{c.CERT}/{cert['id']}/download")
    assert response.status_code == 200
    body = response.json()
    assert body["presigned_url"] == f"/media/{cert['file_path']}"
    assert body["expires_in_seconds"] == 900
    assert body["certificate_id"] == cert["id"]
    assert body["filename"] is None


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A01")
@pytest.mark.skip(reason="blocked: the audit row written by a download is not exposed by any endpoint")
def test_download_writes_audit_row():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A02")
@pytest.mark.xfail(strict=True, reason="TEN-MEDIA-CSCHEMA: /media/<tenant>/... answers 400 without a cschema header, so a generated certificate link cannot be opened by a plain browser request")
def test_media_link_is_public(admin, cert):
    link = admin.get(f"{c.CERT}/{cert['id']}/download").json()["presigned_url"]
    fetched = httpx.get(c.ORIGIN + link, timeout=30)
    assert fetched.status_code == 200
    assert fetched.content == c.PDF_BYTES


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A03")
@pytest.mark.parametrize("role", ["staff", "teacher"])
def test_staff_and_teacher_download_any(role_clients, cert, role):
    assert role_clients[role].get(f"{c.CERT}/{cert['id']}/download").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A04")
def test_student_downloads_own_only(admin, cfam, ctype, cleanup):
    own = c.received(admin, cleanup, cfam.s1.student_id, ctype["id"])
    theirs = c.received(admin, cleanup, cfam.s2.student_id, ctype["id"])
    assert cfam.s1_client.get(f"{c.CERT}/{own['id']}/download").status_code == 200
    denied = cfam.s1_client.get(f"{c.CERT}/{theirs['id']}/download")
    assert denied.status_code == 403
    assert denied.json()["detail"] == "You do not have permission to download this certificate"


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A05")
def test_parent_downloads_linked_child(admin, cfam, ctype, cleanup):
    own = c.received(admin, cleanup, cfam.s1.student_id, ctype["id"])
    theirs = c.received(admin, cleanup, cfam.s2.student_id, ctype["id"])
    assert cfam.p1_client.get(f"{c.CERT}/{own['id']}/download").status_code == 200
    assert cfam.p1_client.get(f"{c.CERT}/{theirs['id']}/download").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A06")
def test_download_unknown_and_malformed(admin):
    missing = admin.get(f"{c.CERT}/{c.UNKNOWN}/download")
    assert missing.status_code == 404
    assert missing.json()["detail"] == f"Certificate with id {c.UNKNOWN} not found"
    assert admin.get(f"{c.CERT}/abc/download").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A07")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 200), ("student", 403), ("parent", 403)]
)
def test_download_permission_matrix(role_clients, cert, role, status):
    assert role_clients[role].get(f"{c.CERT}/{cert['id']}/download").status_code == status


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A08")
def test_download_requires_token(anon, cert):
    assert anon.get(f"{c.CERT}/{cert['id']}/download").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-CER-10-A09")
def test_download_tenant_isolation(admin, tenant_b, tenant_b_name, cert):
    assert tenant_b.get(f"{c.CERT}/{cert['id']}/download").status_code == 404
    assert admin.get(f"{c.CERT}/{cert['id']}/download", headers={"cschema": tenant_b_name}).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-CER-14-A01")
@pytest.mark.tc("TC-CER-14-A02")
@pytest.mark.tc("TC-CER-14-A03")
@pytest.mark.tc("TC-CER-14-A04")
@pytest.mark.tc("TC-CER-14-A05")
@pytest.mark.skip(
    reason="blocked: audit rows and stale registry rows are not exposed by any endpoint, and the cleanup task needs a Celery worker and direct database access"
)
def test_audit_and_stale_cleanup():
    raise AssertionError
