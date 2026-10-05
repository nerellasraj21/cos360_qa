import pytest

from api_tests.fee import helpers as h
from api_tests.support import Api, Cleanup, unique


@pytest.fixture(scope="session")
def year_id(anon):
    years = anon.get("/auth/academic-years").json()
    active = [y for y in years if y.get("is_active")]
    return (active or years)[0]["id"]


@pytest.fixture(scope="session")
def second_year_id(anon, year_id):
    others = [y for y in anon.get("/auth/academic-years").json() if y["id"] != year_id]
    if not others:
        pytest.skip("the QA tenant has no second academic year")
    return others[0]["id"]


@pytest.fixture(scope="session")
def fee_world(admin, year_id):
    academic_year_id = year_id
    stack = Cleanup()
    cls = h.make_class(admin, stack, academic_year_id, sections=("A", "B"))
    category = h.make_category(admin, stack, academic_year_id)
    q4 = h.make_term(admin, stack, academic_year_id, h.Q4_DATES)
    t3 = h.make_term(admin, stack, academic_year_id, h.T3_DATES)
    tuition = h.make_type(admin, stack, academic_year_id, category["id"], q4["id"], name=unique("fee_tuition_"))
    lab = h.make_type(admin, stack, academic_year_id, category["id"], t3["id"], name=unique("fee_lab_"))
    world = {
        "class": cls,
        "category": category,
        "q4": q4,
        "t3": t3,
        "tuition": tuition,
        "lab": lab,
        "q4_dates": sorted(q4["fee_term_dates"], key=lambda x: x["fee_term_date"]),
        "t3_dates": sorted(t3["fee_term_dates"], key=lambda x: x["fee_term_date"]),
    }
    yield world
    stack.run()


@pytest.fixture
def new_student(admin, cleanup, year_id, fee_world):
    def factory(section_name=None):
        return h.make_student(admin, cleanup, year_id, fee_world["class"], section_name)

    return factory


@pytest.fixture
def w1(admin, cleanup, year_id, fee_world, new_student):
    student = new_student()
    mapping = h.map_student(admin, cleanup, year_id, student, fee_world["tuition"]["id"], "12000.00")
    return {"student": student, "mapping": mapping, "tuition": fee_world["tuition"]}


@pytest.fixture
def w2(admin, cleanup, year_id, fee_world, new_student):
    student = new_student()
    tuition = fee_world["tuition"]
    mapping = h.map_student(admin, cleanup, year_id, student, tuition["id"], "12000.00")
    h.ok(
        admin.post(
            "/fee/concessions/bulk",
            json={
                "student_id": student["id"],
                "academic_year_id": year_id,
                "concessions": [
                    {
                        "fee_type_id": tuition["id"],
                        "concession_amount": "2000.00",
                        "reason": "Sibling discount",
                        "approved_by": "principal",
                    }
                ],
            },
        )
    )
    h.ok(h.pay(admin, student, year_id, "4000.00", [(tuition["id"], "4000.00")]))
    return {"student": student, "mapping": mapping, "tuition": tuition}


@pytest.fixture
def mismatched_admin(logins, tenant_b_name):
    client = Api(token=logins["admin"]["access_token"], tenant_header=tenant_b_name)
    yield client
    client.close()




import json
import os

_RESULTS = {}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not os.environ.get("FEE_TC_REPORT"):
        return
    ids = [m.args[0] for m in item.iter_markers("tc") if m.args]
    entry = _RESULTS.setdefault(item.nodeid, {"ids": ids, "outcome": "passed", "reason": ""})
    if report.when == "call":
        if report.skipped:
            entry["outcome"] = "xfailed" if hasattr(report, "wasxfail") else "skipped"
            entry["reason"] = str(getattr(report, "wasxfail", "") or (report.longrepr[2] if isinstance(report.longrepr, tuple) else ""))
        elif report.failed:
            entry["outcome"] = "failed"
        elif hasattr(report, "wasxfail"):
            entry["outcome"] = "xpassed"
    elif report.when == "setup" and report.skipped:
        entry["outcome"] = "skipped"
        entry["reason"] = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else ""
    elif report.when in ("setup", "teardown") and report.failed:
        entry["outcome"] = "error"
    with open(os.environ["FEE_TC_REPORT"], "w") as fh:
        json.dump(_RESULTS, fh)
