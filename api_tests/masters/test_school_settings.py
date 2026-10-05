import base64
import json

import httpx
import pytest

from api_tests.masters.helpers import DENIED
from api_tests.support import API_URL, unique

BASE = "/school-settings"
TEXT_FIELDS = [
    "school_name",
    "contact_no",
    "alt_contact_no",
    "school_email",
    "address",
    "city",
    "state",
    "district",
    "pin_code",
    "country",
    "academic_year",
    "installation_date",
    "school_board",
]
MIB2 = 2 * 1024 * 1024
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 1000


def tenant_id_of(api):
    payload = api.token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["tenant_id"]


def media_get(url):
    root = API_URL.rsplit("/api/v1", 1)[0]
    return httpx.get(root + url, timeout=30)


def snapshot(api):
    response = api.get(BASE)
    if response.status_code == 404:
        return None
    assert response.status_code == 200, response.text
    return response.json()


def restore(api, saved):
    body = {} if saved is None else {k: saved.get(k) for k in TEXT_FIELDS}
    api.put(BASE, json=body)


@pytest.fixture
def guarded(tenant_b, cleanup):
    saved = snapshot(tenant_b)
    cleanup.add(restore, tenant_b, saved)
    return tenant_b


def full_body(**over):
    body = {
        "school_name": unique("mstschool"),
        "contact_no": "9900099000",
        "school_email": "school@example.com",
        "school_board": "CBSE",
        "pin_code": "503001",
        "city": "Hyderabad",
    }
    body.update(over)
    return body


def upload(api, path, name="logo.png", content=PNG, mime="image/png"):
    return api.post(f"{BASE}/{path}", files={"photo": (name, content, mime)})


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A01")
def test_get_settings_before_configuration(admin, tenant_b):
    for client in (tenant_b, admin):
        response = client.get(BASE)
        if response.status_code == 200:
            continue
        assert response.status_code == 404
        assert response.json()["detail"] == "School settings not configured yet."
        return
    pytest.skip("both QA tenants already hold a school settings row; the unconfigured state cannot be recreated")


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A02")
def test_put_settings_and_read_back(guarded):
    body = full_body()
    response = guarded.put(BASE, json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["id"]
    for key, value in body.items():
        assert data[key] == value
    assert guarded.get(BASE).json() == data


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A03")
def test_put_is_full_replace(guarded):
    assert guarded.put(BASE, json=full_body()).status_code == 200
    name = unique("mstschool")
    response = guarded.put(BASE, json={"school_name": name})
    assert response.status_code == 200
    data = response.json()
    assert data["school_name"] == name
    for field in ("contact_no", "school_board", "pin_code", "city", "school_email"):
        assert data[field] is None


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A04")
def test_put_overlong_name_fails(guarded):
    response = guarded.put(BASE, json={"school_name": "n" * 256})
    assert response.status_code == 500
    assert response.json()["detail"] == "An error occurred while saving school settings."


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A05")
def test_put_empty_body_clears_text_fields(guarded):
    assert guarded.put(BASE, json=full_body()).status_code == 200
    response = guarded.put(BASE, json={})
    assert response.status_code == 200
    data = response.json()
    assert all(data[f] is None for f in TEXT_FIELDS)


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A06")
@pytest.mark.xfail(strict=True, reason="TEN-MEDIA-CSCHEMA: /media/<tenant>/... answers 400 without a cschema header, so the saved logo cannot be served")
def test_upload_logo(guarded):
    response = upload(guarded, "upload-image")
    assert response.status_code == 200, response.text
    url = response.json()["image_url"]
    assert url.startswith(f"/media/{tenant_id_of(guarded)}/school/images/")
    served = media_get(url)
    assert served.status_code == 200 and served.content == PNG


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A07")
def test_upload_signature(guarded):
    response = upload(guarded, "upload-signature", name="sign.webp", content=b"RIFF" + b"0" * 200, mime="image/webp")
    assert response.status_code == 200, response.text
    url = response.json()["principal_signature_url"]
    assert url.startswith(f"/media/{tenant_id_of(guarded)}/school/signatures/")
    assert url.endswith(".webp")


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A08")
@pytest.mark.parametrize("name,mime", [("notes.pdf", "application/pdf"), ("logo.gif", "image/gif")])
def test_upload_rejects_other_extensions(guarded, name, mime):
    response = upload(guarded, "upload-image", name=name, content=b"x" * 100, mime=mime)
    assert response.status_code == 400
    assert response.json()["detail"] == "Only jpg, png, webp files are allowed"


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A09")
def test_upload_size_boundary(guarded):
    exact = upload(guarded, "upload-image", content=b"a" * MIB2)
    assert exact.status_code == 200, exact.text
    over = upload(guarded, "upload-image", content=b"a" * (MIB2 + 1))
    assert over.status_code == 400
    assert over.json()["detail"] == "File size must not exceed 2 MB"


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A10")
def test_upload_without_photo_part(guarded):
    response = guarded.post(f"{BASE}/upload-image", files={"other": ("logo.png", PNG, "image/png")})
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A11")
def test_upload_creates_row_when_missing(tenant_b, cleanup):
    saved = snapshot(tenant_b)
    if saved is not None:
        pytest.skip("qa_school_b already holds a settings row, so the create-on-upload path cannot be reached")
    cleanup.add(restore, tenant_b, saved)
    response = upload(tenant_b, "upload-image")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["image_url"] and data["school_name"] is None


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A12")
@pytest.mark.xfail(strict=True, reason="TEN-MEDIA-CSCHEMA: /media/<tenant>/... answers 400 without a cschema header, so the saved logo cannot be served")
def test_reupload_with_other_extension_keeps_old_file(guarded):
    first = upload(guarded, "upload-image", name="logo.png")
    assert first.status_code == 200
    second = upload(guarded, "upload-image", name="logo.jpg", mime="image/jpeg")
    assert second.status_code == 200
    assert second.json()["image_url"].endswith(".jpg")
    assert first.json()["image_url"].endswith(".png")
    assert media_get(first.json()["image_url"]).status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A13")
def test_put_after_upload_keeps_image_url(guarded):
    url = upload(guarded, "upload-image").json()["image_url"]
    response = guarded.put(BASE, json=full_body())
    assert response.status_code == 200
    assert response.json()["image_url"] == url


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A14")
def test_admin_can_read_settings_and_others_are_denied(admin):
    response = admin.get(BASE)
    assert response.status_code in (200, 404)


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A14")
@pytest.mark.parametrize("role", DENIED)
def test_settings_denied_for_other_roles(role_clients, role):
    client = role_clients[role]
    assert client.get(BASE).status_code == 403
    assert client.put(BASE, json={"school_name": unique("mstschool")}).status_code == 403
    assert upload(client, "upload-image").status_code == 403
    assert upload(client, "upload-signature").status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A15")
def test_settings_need_authentication(anon):
    assert anon.get(BASE).status_code == 401
    assert anon.put(BASE, json={}).status_code == 401
    assert upload(anon, "upload-image").status_code == 401
    assert upload(anon, "upload-signature").status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-MST-14-A16")
def test_settings_tenant_isolation(guarded, admin):
    name = unique("mstschool")
    assert guarded.put(BASE, json={"school_name": name}).status_code == 200
    other = admin.get(BASE)
    if other.status_code == 200:
        assert other.json()["school_name"] != name
    else:
        assert other.status_code == 404
    url = upload(guarded, "upload-image").json()["image_url"]
    assert f"/media/{tenant_id_of(guarded)}/" in url
    assert tenant_id_of(guarded) != tenant_id_of(admin)
    assert f"/media/{tenant_id_of(admin)}/" not in url
