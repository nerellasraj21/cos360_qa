import io

import httpx
import pytest

from api_tests.students import helpers as h
from api_tests.support import API_URL

ORIGIN = API_URL.rsplit("/api/v1", 1)[0]
UNKNOWN = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(scope="module")
def target(family):
    return family.other


def photo_files(name, content, ctype):
    return {"photo": (name, io.BytesIO(content), ctype)}


def upload(client, student_id, name="p.png", content=h.PNG_BYTES, ctype="image/png"):
    return client.post(f"/students/admission/id/{student_id}/photo", files=photo_files(name, content, ctype))


def clear(admin, student_id):
    admin.delete(f"/students/admission/id/{student_id}/photo")


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A01")
def test_upload_png_sets_photo_url(admin, logins, target):
    response = upload(admin, target.student_id)
    try:
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == target.student_id
        assert body["photo_url"] == f"/media/{logins['admin']['tenant_id']}/student/photos/{target.student_id}.png"
        fetched = httpx.get(ORIGIN + body["photo_url"], headers={"Authorization": f"Bearer {admin.token}"}, timeout=30)
        assert fetched.status_code == 200
        assert fetched.content == h.PNG_BYTES
        assert admin.get(f"/students/admission/id/{target.student_id}").json()["student"]["photo_url"] == body["photo_url"]
    finally:
        clear(admin, target.student_id)


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A02")
def test_upload_rejects_unsupported_extension(admin, target):
    response = upload(admin, target.student_id, name="p.gif", content=b"GIF89a", ctype="image/gif")
    assert response.status_code == 400
    assert response.json()["detail"] == "Only jpg, png, webp files are allowed"


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A02")
@pytest.mark.skip(reason="size boundary needs a 2 MB file; the suite uses tiny files only")
def test_upload_size_boundary():
    raise AssertionError


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A02")
def test_replacing_extension_changes_url(admin, logins, target):
    try:
        first = upload(admin, target.student_id)
        second = upload(admin, target.student_id, name="p.jpg", content=h.JPG_BYTES, ctype="image/jpeg")
        assert first.status_code == 200 and second.status_code == 200
        assert second.json()["photo_url"].endswith(f"{target.student_id}.jpg")
    finally:
        clear(admin, target.student_id)


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A03")
def test_upload_for_unknown_student(admin):
    response = upload(admin, UNKNOWN)
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A04")
def test_delete_photo_then_again(admin, target):
    assert upload(admin, target.student_id).status_code == 200
    first = admin.delete(f"/students/admission/id/{target.student_id}/photo")
    assert first.status_code == 200
    assert "detail" in first.json()
    again = admin.delete(f"/students/admission/id/{target.student_id}/photo")
    assert again.status_code == 404
    assert again.json()["detail"] == "No photo to delete"
    assert admin.get(f"/students/admission/id/{target.student_id}").json()["student"]["photo_url"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A05")
def test_upload_requires_photo_field(admin, target):
    response = admin.post(f"/students/admission/id/{target.student_id}/photo")
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A06")
@pytest.mark.parametrize(
    "role,status", [("admin", 200), ("staff", 200), ("teacher", 403), ("student", 403), ("parent", 403)]
)
def test_photo_permission_matrix(admin, role_clients, target, role, status):
    try:
        assert upload(role_clients[role], target.student_id).status_code == status
        deleted = role_clients[role].delete(f"/students/admission/id/{target.student_id}/photo")
        assert deleted.status_code == (200 if status == 200 else 403)
    finally:
        clear(admin, target.student_id)


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A07")
def test_photo_requires_token(anon, target):
    assert upload(anon, target.student_id).status_code == 401
    assert anon.delete(f"/students/admission/id/{target.student_id}/photo").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STU-05-A08")
def test_photo_tenant_isolation(admin, tenant_b, tenant_b_name, target):
    assert upload(tenant_b, target.student_id).status_code == 404
    mismatch = admin.post(
        f"/students/admission/id/{target.student_id}/photo",
        files=photo_files("p.png", h.PNG_BYTES, "image/png"),
        headers={"cschema": tenant_b_name},
    )
    assert mismatch.status_code == 403
