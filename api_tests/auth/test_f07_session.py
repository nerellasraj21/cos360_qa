import base64
import json

import pytest

from api_tests.auth.helpers import MISSING_AUTH, claims_of, detail_text
from api_tests.support import QA_TENANT


@pytest.fixture
def session_user(new_staff):
    user = new_staff("Staff")
    return user, user.activate()


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-07-A01")
def test_access_token_is_stateless(session_user, api_client):
    _, data = session_user
    client = api_client(token=data["access_token"])
    for _ in range(3):
        assert client.get("/auth/available-resources").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-07-A02")
def test_refresh_token_is_not_a_bearer(session_user, api_client):
    _, data = session_user
    client = api_client(token=data["refresh_token"])
    response = client.get("/auth/available-resources")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token type"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-07-A03")
def test_access_token_is_not_a_refresh_token(session_user, anon):
    _, data = session_user
    response = anon.post("/auth/refresh", json={"refresh_token": data["access_token"]})
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token type"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-07-A04")
def test_tampered_payload_rejected(session_user, api_client):
    _, data = session_user
    header, payload, signature = data["access_token"].split(".")
    padded = payload + "=" * (-len(payload) % 4)
    body = json.loads(base64.urlsafe_b64decode(padded))
    body["role"] = "Admin"
    forged = base64.urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip("=")
    client = api_client(token=f"{header}.{forged}.{signature}")
    response = client.get("/auth/available-resources")
    assert response.status_code == 401
    assert detail_text(response) == "Invalid token"


@pytest.mark.api
@pytest.mark.tc("TC-AUTH-07-A05")
def test_authorization_scheme_must_be_bearer(session_user, api_client):
    _, data = session_user
    client = api_client(tenant_header=QA_TENANT)
    wrong = client.get("/auth/available-resources", headers={"Authorization": "Token abc"})
    assert wrong.status_code == 401
    assert detail_text(wrong) == MISSING_AUTH
    missing = client.get("/auth/available-resources")
    assert missing.status_code == 401
    assert detail_text(missing) == MISSING_AUTH
    assert claims_of(data["access_token"])["token_type"] == "access"
