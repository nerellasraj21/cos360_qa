import re
import uuid

import httpx
import pytest

from api_tests.staff.helpers import granted
from api_tests.support import API_URL, QA_TENANT

LEVELS = ["Below Graduation", "Graduation", "Post Graduation", "PhD"]
MEDIA_ROOT = API_URL.rsplit("/api/", 1)[0]


def qual_body(**overrides):
    body = {"level": "Graduation", "name": "B.Sc", "passed_out_year": 2015, "percentage": 78.5, "university": "Osmania"}
    body.update(overrides)
    return body


def add_qual(admin, staff_id, **overrides):
    response = admin.post(f"/staff/{staff_id}/qualifications", json=qual_body(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A01")
def test_add_qualification(admin, make_staff):
    staff = make_staff()
    response = admin.post(f"/staff/{staff['id']}/qualifications", json=qual_body())
    assert response.status_code == 201
    data = response.json()
    assert data["percentage"] == "78.50"
    assert data["staff_id"] == staff["id"]
    assert set(data) == {"id", "staff_id", "level", "name", "passed_out_year", "percentage", "university"}


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A02")
def test_one_qualification_per_level(admin, make_staff):
    staff = make_staff()
    for level in LEVELS:
        add_qual(admin, staff["id"], level=level, name=f"deg {level}")
    listed = admin.get(f"/staff/{staff['id']}/qualifications").json()
    assert sorted(q["level"] for q in listed) == sorted(LEVELS)


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A03")
def test_invalid_level(admin, make_staff):
    staff = make_staff()
    assert admin.post(f"/staff/{staff['id']}/qualifications", json=qual_body(level="Masters")).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A04")
@pytest.mark.parametrize("missing", ["level", "name"])
def test_missing_level_or_name_is_not_accepted(admin, make_staff, missing):
    staff = make_staff()
    body = qual_body()
    del body[missing]
    response = admin.post(f"/staff/{staff['id']}/qualifications", json=body)
    assert response.status_code == 400
    assert admin.get(f"/staff/{staff['id']}/qualifications").json() == []


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A05")
def test_percentage_boundaries(admin, make_staff):
    staff = make_staff()
    assert add_qual(admin, staff["id"], percentage=100.0)["percentage"] == "100.00"
    assert add_qual(admin, staff["id"], percentage=999.99)["percentage"] == "999.99"
    response = admin.post(f"/staff/{staff['id']}/qualifications", json=qual_body(percentage=1000))
    assert response.status_code >= 400


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A06")
def test_unknown_staff_on_post_and_get(admin):
    missing = str(uuid.uuid4())
    post = admin.post(f"/staff/{missing}/qualifications", json=qual_body())
    get = admin.get(f"/staff/{missing}/qualifications")
    assert post.status_code == 404 and get.status_code == 404
    assert post.json()["detail"] == "Staff not found"
    assert get.json()["detail"] == "Staff not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A07")
def test_list_qualifications(admin, make_staff):
    staff = make_staff()
    add_qual(admin, staff["id"], name="B.Sc")
    add_qual(admin, staff["id"], level="Post Graduation", name="M.Sc")
    response = admin.get(f"/staff/{staff['id']}/qualifications")
    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {q["name"] for q in response.json()} == {"B.Sc", "M.Sc"}


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A08")
def test_partial_update(admin, make_staff):
    staff = make_staff()
    qual = add_qual(admin, staff["id"])
    response = admin.put(f"/staff/{staff['id']}/qualifications/{qual['id']}", json={"percentage": 82})
    assert response.status_code == 200
    data = response.json()
    assert data["percentage"] == "82.00"
    assert data["name"] == qual["name"] and data["university"] == qual["university"]
    assert data["level"] == qual["level"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A09")
def test_qualification_of_another_staff_is_not_found(admin, make_staff):
    owner = make_staff()
    other = make_staff()
    qual = add_qual(admin, owner["id"])
    put = admin.put(f"/staff/{other['id']}/qualifications/{qual['id']}", json={"percentage": 1})
    delete = admin.delete(f"/staff/{other['id']}/qualifications/{qual['id']}")
    assert put.status_code == 404 and delete.status_code == 404
    assert put.json()["detail"] == "Qualification not found"
    assert len(admin.get(f"/staff/{owner['id']}/qualifications").json()) == 1


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A10")
def test_delete_qualification(admin, make_staff):
    staff = make_staff()
    qual = add_qual(admin, staff["id"])
    response = admin.delete(f"/staff/{staff['id']}/qualifications/{qual['id']}")
    assert response.status_code == 200
    assert response.json() == {"detail": "Qualification deleted successfully"}
    assert admin.get(f"/staff/{staff['id']}/qualifications").json() == []
    assert admin.delete(f"/staff/{staff['id']}/qualifications/{qual['id']}").status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A11")
def test_qualifications_removed_with_staff(admin, make_staff):
    staff = make_staff()
    add_qual(admin, staff["id"])
    assert admin.delete(f"/staff/enrollment/{staff['id']}").status_code == 200
    assert admin.get(f"/staff/{staff['id']}/qualifications").status_code == 404
    assert admin.get(f"/staff/enrollment/{staff['id']}").status_code == 404


def qual_calls(staff_id, qual_id):
    return [
        ("create", "POST", f"/staff/{staff_id}/qualifications", qual_body(), "update"),
        ("read", "GET", f"/staff/{staff_id}/qualifications", None, "read"),
        ("update", "PUT", f"/staff/{staff_id}/qualifications/{qual_id}", {"percentage": 50}, "update"),
        ("delete", "DELETE", f"/staff/{staff_id}/qualifications/{qual_id}", None, "delete"),
    ]


@pytest.mark.api
@pytest.mark.parametrize(
    "role",
    [
        pytest.param("staff", marks=pytest.mark.tc("TC-STF-04-A12")),
        pytest.param("teacher", marks=pytest.mark.tc("TC-STF-04-A13")),
        pytest.param("student", marks=pytest.mark.tc("TC-STF-04-A13")),
        pytest.param("parent", marks=pytest.mark.tc("TC-STF-04-A13")),
    ],
)
def test_qualification_role_matrix(role_clients, logins, make_staff, role):
    admin = role_clients["admin"]
    staff = make_staff()
    qual = add_qual(admin, staff["id"])
    client = role_clients[role]
    for _, method, path, body, action in qual_calls(staff["id"], qual["id"]):
        if granted(logins, role, "staff", action):
            if method == "GET":
                assert client.request(method, path).status_code == 200
            continue
        kwargs = {"json": body} if body is not None else {}
        assert client.request(method, path, **kwargs).status_code == 403, (role, method)
    assert admin.get(f"/staff/{staff['id']}/qualifications").json()[0]["id"] == qual["id"]


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A14")
def test_admin_on_all_qualification_endpoints(admin, make_staff):
    staff = make_staff()
    qual = add_qual(admin, staff["id"])
    assert admin.get(f"/staff/{staff['id']}/qualifications").status_code == 200
    assert admin.put(f"/staff/{staff['id']}/qualifications/{qual['id']}", json={"name": "Updated"}).status_code == 200
    assert admin.delete(f"/staff/{staff['id']}/qualifications/{qual['id']}").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A15")
def test_qualifications_require_token(anon):
    staff_id, qual_id = str(uuid.uuid4()), str(uuid.uuid4())
    for _, method, path, body, _a in qual_calls(staff_id, qual_id):
        kwargs = {"json": body} if body is not None else {}
        assert anon.request(method, path, **kwargs).status_code == 401, (method, path)


@pytest.mark.api
@pytest.mark.tc("TC-STF-04-A16")
def test_qualifications_tenant_isolation(admin, tenant_b, make_staff):
    staff = make_staff()
    qual = add_qual(admin, staff["id"])
    post = tenant_b.post(f"/staff/{staff['id']}/qualifications", json=qual_body())
    assert post.status_code == 404 and post.json()["detail"] == "Staff not found"
    assert tenant_b.get(f"/staff/{staff['id']}/qualifications").status_code == 404
    assert tenant_b.put(f"/staff/{staff['id']}/qualifications/{qual['id']}", json={"name": "x"}).status_code == 404
    assert len(admin.get(f"/staff/{staff['id']}/qualifications").json()) == 1


def photo_files(name, data, mime="image/png"):
    return {"photo": (name, data, mime)}


def media_get(url, with_tenant=True):
    headers = {"cschema": QA_TENANT} if with_tenant else {}
    return httpx.get(MEDIA_ROOT + url, headers=headers, timeout=30)


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A01")
def test_upload_photo(admin, make_staff):
    staff = make_staff()
    response = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("p.png", b"p" * 100_000))
    assert response.status_code == 200
    url = response.json()["photo_url"]
    assert re.fullmatch(rf"/media/[0-9a-f-]{{36}}/staff/photos/{staff['id']}\.png", url)
    assert media_get(url).content == b"p" * 100_000


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A02")
def test_photo_is_served_without_authorization(admin, make_staff):
    staff = make_staff()
    url = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("p.png", b"pub")).json()["photo_url"]
    response = media_get(url)
    assert response.status_code == 200
    assert response.content == b"pub"


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A02")
@pytest.mark.xfail(
    strict=True,
    reason="D-STF-04: GET /media/... without a cschema header returns 500 (tenant middleware raises for a non-API path); an img tag cannot send the header",
)
def test_photo_served_to_a_plain_browser_request(admin, make_staff):
    staff = make_staff()
    url = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("p.png", b"pub")).json()["photo_url"]
    response = media_get(url, with_tenant=False)
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A03")
def test_photo_extension_check(admin, make_staff):
    staff = make_staff()
    gif = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.gif", b"gif", "image/gif"))
    assert gif.status_code == 400
    assert gif.json()["detail"] == "Only jpg, png, webp files are allowed"
    noext = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("photo", b"x"))
    assert noext.status_code == 400
    fake = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("fake.png", b"this is plain text"))
    assert fake.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A04")
def test_photo_size_boundary(admin, make_staff):
    staff = make_staff()
    exact = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.jpg", b"x" * 2097152, "image/jpeg"))
    assert exact.status_code == 200
    over = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.jpg", b"x" * 2097153, "image/jpeg"))
    assert over.status_code == 400
    assert over.json()["detail"] == "File size must not exceed 2 MB"


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A05")
def test_replacing_with_other_extension_removes_old_file(admin, make_staff):
    staff = make_staff()
    first = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.png", b"png"))
    png_url = first.json()["photo_url"]
    assert media_get(png_url).status_code == 200
    second = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.jpg", b"jpg", "image/jpeg"))
    assert second.json()["photo_url"].endswith(".jpg")
    assert media_get(png_url).status_code == 404
    assert media_get(second.json()["photo_url"]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A06")
def test_photo_part_is_required(admin, make_staff):
    staff = make_staff()
    assert admin.post(f"/staff/enrollment/{staff['id']}/photo").status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A07")
def test_photo_unknown_staff(admin):
    missing = str(uuid.uuid4())
    post = admin.post(f"/staff/enrollment/{missing}/photo", files=photo_files("a.png", b"x"))
    delete = admin.delete(f"/staff/enrollment/{missing}/photo")
    assert post.status_code == 404 and delete.status_code == 404
    assert post.json()["detail"] == "Staff not found"


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A08")
def test_delete_photo_twice(admin, make_staff):
    staff = make_staff()
    url = admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.png", b"x")).json()["photo_url"]
    first = admin.delete(f"/staff/enrollment/{staff['id']}/photo")
    assert first.status_code == 200
    assert first.json() == {"detail": "Staff photo deleted successfully"}
    assert media_get(url).status_code == 404
    second = admin.delete(f"/staff/enrollment/{staff['id']}/photo")
    assert second.status_code == 404
    assert second.json()["detail"] == "No photo to delete"
    assert admin.get(f"/staff/enrollment/{staff['id']}").json()["photo_url"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A09")
@pytest.mark.parametrize("role", ["staff", "teacher", "student", "parent"])
def test_photo_denied_for_non_admin_roles(role_clients, logins, make_staff, role):
    assert not granted(logins, role, "staff", "update")
    staff = make_staff()
    client = role_clients[role]
    assert client.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.png", b"x")).status_code == 403
    assert client.delete(f"/staff/enrollment/{staff['id']}/photo").status_code == 403
    assert role_clients["admin"].get(f"/staff/enrollment/{staff['id']}").json()["photo_url"] is None


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A10")
def test_photo_requires_token(anon):
    missing = str(uuid.uuid4())
    assert anon.post(f"/staff/enrollment/{missing}/photo", files=photo_files("a.png", b"x")).status_code == 401
    assert anon.delete(f"/staff/enrollment/{missing}/photo").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-STF-05-A11")
def test_photo_tenant_isolation(admin, tenant_b, make_staff):
    staff = make_staff()
    admin.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.png", b"x"))
    post = tenant_b.post(f"/staff/enrollment/{staff['id']}/photo", files=photo_files("a.png", b"y"))
    assert post.status_code == 404 and post.json()["detail"] == "Staff not found"
    assert tenant_b.delete(f"/staff/enrollment/{staff['id']}/photo").status_code == 404
    assert admin.get(f"/staff/enrollment/{staff['id']}").json()["photo_url"] is not None
