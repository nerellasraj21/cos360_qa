import pytest

from api_tests.exam.helpers import OTHER_ROLES, ALL_ROLES, settings_lock

FULL = {
    "default_board": "State",
    "custom_board_name": "Board X",
    "hall_ticket_min_attendance": 80,
    "hall_ticket_min_fee_paid_pct": 50,
    "grace_max_per_subject": 3,
    "grace_max_subjects": 2,
    "grace_auto_apply": True,
    "reconduct_max_failed_subjects": 4,
}
NEUTRAL = {"hall_ticket_min_attendance": 75, "grace_auto_apply": False, "reconduct_max_failed_subjects": 2}


@pytest.fixture
def settings_guard(admin):
    with settings_lock():
        before = admin.get("/exam-settings")
        yield
        if before.status_code == 200:
            data = before.json()
            data.pop("id", None)
            admin.put("/exam-settings", json=data)
        else:
            admin.put("/exam-settings", json=NEUTRAL)


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A01")
def test_get_settings_when_never_configured(tenant_b):
    response = tenant_b.get("/exam-settings")
    assert response.status_code == 404
    assert response.json()["detail"] == "Exam settings not configured yet."


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A02")
def test_put_then_get_full_settings(admin, settings_guard):
    put = admin.put("/exam-settings", json=FULL)
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["id"]
    got = admin.get("/exam-settings")
    assert got.status_code == 200
    data = got.json()
    assert data["id"] == body["id"]
    assert data["hall_ticket_min_attendance"] == "80.00"
    assert data["hall_ticket_min_fee_paid_pct"] == "50.00"
    assert data["default_board"] == "State"
    assert data["custom_board_name"] == "Board X"
    assert data["grace_max_per_subject"] == 3
    assert data["grace_max_subjects"] == 2
    assert data["grace_auto_apply"] is True
    assert data["reconduct_max_failed_subjects"] == 4


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A03")
def test_put_overwrites_every_field(admin, settings_guard):
    first = admin.put("/exam-settings", json=FULL).json()
    second = admin.put("/exam-settings", json={"hall_ticket_min_attendance": 70})
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first["id"]
    data = admin.get("/exam-settings").json()
    assert data["hall_ticket_min_attendance"] == "70.00"
    assert data["hall_ticket_min_fee_paid_pct"] is None
    assert data["default_board"] is None
    assert data["custom_board_name"] is None
    assert data["grace_max_per_subject"] is None
    assert data["grace_max_subjects"] is None
    assert data["grace_auto_apply"] is False
    assert data["reconduct_max_failed_subjects"] == 2


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A04")
@pytest.mark.parametrize(
    "body",
    [
        {"hall_ticket_min_attendance": 101},
        {"hall_ticket_min_attendance": -1},
        {"hall_ticket_min_fee_paid_pct": 101},
    ],
)
def test_percentage_bounds_rejected(admin, settings_guard, body):
    assert admin.put("/exam-settings", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A05")
@pytest.mark.parametrize(
    "body",
    [{"grace_max_per_subject": 101}, {"grace_max_subjects": 51}, {"reconduct_max_failed_subjects": -1}],
)
def test_grace_and_reconduct_bounds_rejected(admin, settings_guard, body):
    assert admin.put("/exam-settings", json=body).status_code == 422


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A06")
def test_percentage_boundaries_accepted(admin, settings_guard):
    response = admin.put("/exam-settings", json={"hall_ticket_min_attendance": 0, "hall_ticket_min_fee_paid_pct": 100})
    assert response.status_code == 200, response.text
    data = admin.get("/exam-settings").json()
    assert data["hall_ticket_min_attendance"] == "0.00"
    assert data["hall_ticket_min_fee_paid_pct"] == "100.00"
    response = admin.put("/exam-settings", json={"hall_ticket_min_attendance": 100, "hall_ticket_min_fee_paid_pct": 0})
    assert response.status_code == 200
    data = admin.get("/exam-settings").json()
    assert data["hall_ticket_min_attendance"] == "100.00"
    assert data["hall_ticket_min_fee_paid_pct"] == "0.00"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A07")
def test_default_board_not_validated(admin, settings_guard):
    response = admin.put("/exam-settings", json={"default_board": "Anything", "hall_ticket_min_attendance": 75})
    assert response.status_code == 200
    assert admin.get("/exam-settings").json()["default_board"] == "Anything"


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A08")
@pytest.mark.parametrize("role", ALL_ROLES)
def test_get_settings_all_roles(role_clients, admin, settings_guard, role):
    admin.put("/exam-settings", json=NEUTRAL)
    assert role_clients[role].get("/exam-settings").status_code == 200


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A09")
@pytest.mark.parametrize("role", OTHER_ROLES)
def test_put_settings_denied(role_clients, role):
    assert role_clients[role].put("/exam-settings", json=NEUTRAL).status_code == 403


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A10")
def test_settings_unauthenticated(anon):
    assert anon.get("/exam-settings").status_code == 401
    assert anon.put("/exam-settings", json=NEUTRAL).status_code == 401


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A11")
def test_settings_tenant_isolation(admin, tenant_b, settings_guard):
    mine = admin.put("/exam-settings", json={**NEUTRAL, "hall_ticket_min_attendance": 77, "default_board": "exm_iso"}).json()
    other = tenant_b.get("/exam-settings")
    if other.status_code == 200:
        assert other.json()["id"] != mine["id"]
        assert other.json()["default_board"] != "exm_iso"
    else:
        assert other.status_code == 404


@pytest.mark.api
@pytest.mark.tc("TC-EXM-01-A12")
def test_settings_cschema_mismatch(foreign):
    assert foreign.get("/exam-settings").status_code == 403
    assert foreign.put("/exam-settings", json=NEUTRAL).status_code == 403
