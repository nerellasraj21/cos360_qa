import httpx
import pytest

from api_tests.auth.helpers import detail_text
from api_tests.support import API_URL, unique
from api_tests.tenants_admin.conftest import MISSING_AUTH, NON_ADMIN, denied_text

ROOT = API_URL[: -len("/api/v1")] if API_URL.endswith("/api/v1") else API_URL
FIELDS = [
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
FULL = {
    "school_name": "Tenadm Public School",
    "contact_no": "9900099000",
    "alt_contact_no": "9999900000",
    "school_email": "school@example.com",
    "address": "1 Main Road",
    "city": "Khammam",
    "state": "Telangana",
    "district": "Khammam",
    "pin_code": "507001",
    "country": "India",
    "academic_year": "2026-27",
    "installation_date": "2020-06-01",
    "school_board": "CBSE",
}


def png(size: int) -> bytes:
    head = b"\x89PNG\r\n\x1a\n"
    return head + b"0" * (size - len(head))


def upload(client, path, name, content, content_type="image/png", field="photo"):
    return client.post(path, files={field: (name, content, content_type)})


@pytest.fixture
def settings_admin(tmp_main):
    return tmp_main.admin


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A01")
def test_get_settings_before_any_save_404(tmp_edge):
    response = tmp_edge.admin.get("/school-settings")
    if response.status_code == 200:
        pytest.skip("the reserved tenant already holds a settings record from an earlier run")
    assert response.status_code == 404
    assert detail_text(response) == "School settings not configured yet."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A02")
def test_put_all_fields(settings_admin):
    response = settings_admin.put("/school-settings", json=FULL)
    assert response.status_code == 200
    body = response.json()
    for key, value in FULL.items():
        assert body[key] == value
    assert body["id"]
    assert "image_url" in body and "principal_signature_url" in body


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A03")
def test_get_returns_saved_values(settings_admin):
    settings_admin.put("/school-settings", json=FULL)
    body = settings_admin.get("/school-settings").json()
    for key, value in FULL.items():
        assert body[key] == value


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A04")
def test_put_replaces_all_fields(settings_admin):
    settings_admin.put("/school-settings", json=FULL)
    response = settings_admin.put("/school-settings", json={"school_name": "Only Name"})
    assert response.status_code == 200
    body = response.json()
    assert body["school_name"] == "Only Name"
    for key in FIELDS[1:]:
        assert body[key] is None


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A05")
def test_put_empty_body_nulls_everything(settings_admin):
    settings_admin.put("/school-settings", json=FULL)
    response = settings_admin.put("/school-settings", json={})
    assert response.status_code == 200
    assert all(response.json()[key] is None for key in FIELDS)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A06")
def test_no_server_side_format_validation(settings_admin):
    response = settings_admin.put(
        "/school-settings", json={"school_name": "x", "contact_no": "abc", "pin_code": "12", "school_email": "x"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contact_no"] == "abc" and body["pin_code"] == "12" and body["school_email"] == "x"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A07")
def test_bad_installation_date_422(settings_admin):
    response = settings_admin.put("/school-settings", json={"school_name": "x", "installation_date": "2026-13-45"})
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A08")
def test_upload_image(settings_admin, tmp_main):
    response = upload(settings_admin, "/school-settings/upload-image", "logo.png", png(100 * 1024))
    assert response.status_code == 200
    assert response.json()["image_url"] == f"/media/{tmp_main.tenant_id}/school/images/school_image_url.png"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A09")
@pytest.mark.xfail(strict=True, reason="TEN-MEDIA-CSCHEMA: GET /media/<tenant>/... without a cschema header returns 400 instead of serving the file publicly")
def test_media_is_public(settings_admin, tmp_main):
    url = upload(settings_admin, "/school-settings/upload-image", "logo.png", png(2048)).json()["image_url"]
    fetched = httpx.get(f"{ROOT}{url}", timeout=30)
    assert fetched.status_code == 200, fetched.text
    assert fetched.content == png(2048)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A10")
def test_upload_signature(settings_admin):
    response = upload(settings_admin, "/school-settings/upload-signature", "sign.jpg", b"\xff\xd8\xff" + b"0" * 500, "image/jpeg")
    assert response.status_code == 200
    assert response.json()["principal_signature_url"].endswith("school_principal_signature_url.jpg")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A11")
def test_upload_gif_rejected(settings_admin):
    response = upload(settings_admin, "/school-settings/upload-image", "logo.gif", b"GIF89a" + b"0" * 100, "image/gif")
    assert response.status_code == 400
    assert detail_text(response) == "Only jpg, png, webp files are allowed"


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A12")
def test_upload_size_boundary(settings_admin):
    too_big = upload(settings_admin, "/school-settings/upload-image", "big.png", png(2_097_153))
    assert too_big.status_code == 400
    assert detail_text(too_big) == "File size must not exceed 2 MB"
    exact = upload(settings_admin, "/school-settings/upload-image", "exact.png", png(2_097_152))
    assert exact.status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A13")
def test_extension_is_lowercased(settings_admin):
    response = upload(settings_admin, "/school-settings/upload-image", "x.PNG", png(512))
    assert response.status_code == 200
    assert response.json()["image_url"].endswith(".png")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A14")
def test_second_upload_with_other_extension_changes_url(settings_admin):
    first = upload(settings_admin, "/school-settings/upload-image", "a.png", png(512)).json()["image_url"]
    second = upload(settings_admin, "/school-settings/upload-image", "a.jpg", b"\xff\xd8\xff" + b"0" * 300, "image/jpeg")
    assert second.status_code == 200
    assert first.endswith(".png") and second.json()["image_url"].endswith(".jpg")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A15")
def test_upload_with_wrong_field_name_422(settings_admin):
    response = upload(settings_admin, "/school-settings/upload-image", "a.png", png(512), field="file")
    assert response.status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A16")
def test_upload_on_tenant_without_record_creates_it(tmp_edge):
    admin = tmp_edge.admin
    existing = admin.get("/school-settings")
    if existing.status_code == 200:
        pytest.skip("the reserved tenant already holds a settings record from an earlier run")
    response = upload(admin, "/school-settings/upload-image", "a.png", png(512))
    assert response.status_code == 200
    body = response.json()
    assert body["image_url"]
    assert all(body[key] is None for key in FIELDS)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A17")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_get_settings_denied_for_non_admin(role_clients, logins, role):
    response = role_clients[role].get("/school-settings")
    assert response.status_code == 403
    assert detail_text(response) == denied_text(logins[role]["role"]["name"], "read", "school_settings")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A17")
def test_get_settings_allowed_for_admin(admin):
    assert admin.get("/school-settings").status_code in (200, 404)


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A18")
@pytest.mark.parametrize("role", NON_ADMIN)
def test_write_settings_denied_for_non_admin(role_clients, logins, role):
    client = role_clients[role]
    name = logins[role]["role"]["name"]
    calls = [
        client.put("/school-settings", json={"school_name": "never"}),
        upload(client, "/school-settings/upload-image", "a.png", png(64)),
        upload(client, "/school-settings/upload-signature", "a.png", png(64)),
    ]
    for response in calls:
        assert response.status_code == 403
        assert detail_text(response) == denied_text(name, "update", "school_settings")


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A19")
def test_settings_require_token(anon):
    calls = [
        anon.get("/school-settings"),
        anon.put("/school-settings", json={}),
        upload(anon, "/school-settings/upload-image", "a.png", png(64)),
    ]
    for response in calls:
        assert response.status_code == 401
        assert detail_text(response) == MISSING_AUTH


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A20")
def test_settings_of_one_tenant_not_visible_to_another(settings_admin, tenant_b):
    name = unique("Tenadm School ")
    assert settings_admin.put("/school-settings", json={"school_name": name}).status_code == 200
    response = tenant_b.get("/school-settings")
    if response.status_code == 200:
        assert response.json()["school_name"] != name
    else:
        assert response.status_code == 404
        assert detail_text(response) == "School settings not configured yet."


@pytest.mark.api
@pytest.mark.tc("TC-TEN-12-A21")
def test_media_paths_carry_tenant_ids(settings_admin, tmp_main, tenant_id):
    url = upload(settings_admin, "/school-settings/upload-image", "a.png", png(512)).json()["image_url"]
    assert f"/{tmp_main.tenant_id}/" in url
    assert f"/{tenant_id}/" not in url
