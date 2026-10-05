import io
import os

from api_tests.students.helpers import DOCX_BYTES, JPG_BYTES, PDF_BYTES, PNG_BYTES, iso, today  # noqa: F401
from api_tests.support import API_URL, BACKEND_ROOT

UNKNOWN = "00000000-0000-0000-0000-000000000001"
ORIGIN = API_URL.rsplit("/api/v1", 1)[0]
CERT = "/certificates"
ISSUE = "/issuable-certificates"
CERT_KEYS = {
    "id",
    "student_id",
    "certificate_type_id",
    "type_name",
    "file_path",
    "issue_date",
    "remarks",
    "certificate_category",
    "issued_by_name",
    "issuer_signature_url",
    "created_at",
    "updated_at",
}


def file_part(name="c.pdf", content=PDF_BYTES, ctype="application/pdf", field="file"):
    return {field: (name, io.BytesIO(content), ctype)}


def send_received(client, student_id, type_id, remarks=None, **file_kwargs):
    data = {"student_id": student_id, "certificate_type_id": type_id}
    if remarks is not None:
        data["remarks"] = remarks
    return client.post(f"{CERT}/received", data=data, files=file_part(**file_kwargs))


def send_issued(client, student_id, type_id, issue_date=None, remarks=None, **file_kwargs):
    data = {"student_id": student_id, "certificate_type_id": type_id}
    if issue_date is not None:
        data["issue_date"] = issue_date
    if remarks is not None:
        data["remarks"] = remarks
    return client.post(f"{CERT}/issued", data=data, files=file_part(**file_kwargs))


def send_legacy(client, student_id, type_id, issue_date=None, **file_kwargs):
    data = {"student_id": student_id, "certificate_type_id": type_id}
    if issue_date is not None:
        data["issue_date"] = issue_date
    return client.post(f"{CERT}/", data=data, files=file_part(**file_kwargs))


def received(admin, cleanup, student_id, type_id, **kwargs):
    response = send_received(admin, student_id, type_id, **kwargs)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{CERT}/{response.json()['id']}")
    return response.json()


def issued(admin, cleanup, student_id, type_id, issue_date=None, **kwargs):
    response = send_issued(admin, student_id, type_id, issue_date or iso(today()), **kwargs)
    assert response.status_code == 201, response.text
    cleanup.delete_later(admin, f"{CERT}/{response.json()['id']}")
    return response.json()


def media_path(key):
    return os.path.join(BACKEND_ROOT, "media", key.replace("/", os.sep))


def stale_path(key):
    return os.path.join(BACKEND_ROOT, "media", "stale", key.replace("/", os.sep))


def ids_of(response):
    return [item["id"] for item in response.json()["items"]]
