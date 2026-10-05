import uuid

from api_tests.support import QA_B_TENANT, QA_TENANT, Api, login, unique

ROLES = ["admin", "staff", "teacher", "student", "parent"]
READ_ROLES = ["admin", "staff", "teacher"]


def other_tenant_header(client):
    return Api(token=client.token, tenant_header=QA_B_TENANT)


def make_route_type(admin, cleanup, **over):
    body = {"type_name": unique("trn_rt_")}
    body.update(over)
    response = admin.post("/masters/route-types/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/route-types/{data['id']}")
    return data


def make_trip_type(admin, cleanup, **over):
    body = {"type_name": unique("trn_tt_")}
    body.update(over)
    response = admin.post("/masters/trip-types/", json=body)
    assert response.status_code == 200, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/trip-types/{data['id']}")
    return data


def make_route(admin, cleanup, **over):
    body = {
        "route_name": unique("trn_route_"),
        "starting_stop": "School",
        "ending_stop": "Market",
        "number_of_stops": 3,
        "start_time": "07:00:00",
        "end_time": "08:30:00",
    }
    body.update(over)
    response = admin.post("/masters/routes/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/routes/{data['id']}")
    return data


def stop_body(route_id, number=1, **over):
    body = {
        "route_id": route_id,
        "name": unique("trn_stop_"),
        "number": number,
        "reaching_time": "07:10:00",
        "pickup_time": "07:10:00",
        "drop_time": "08:20:00",
        "fees": 1200,
    }
    body.update(over)
    return body


def make_stop(admin, cleanup, route_id, number=1, **over):
    response = admin.post("/masters/route-stops/", json=stop_body(route_id, number, **over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/route-stops/{data['id']}")
    return data


def vehicle_body(**over):
    reg = unique("TRN").upper()
    body = {
        "name": unique("trn_bus_"),
        "registration_number": reg,
        "vehicle_type": "Bus",
        "last_inspected_date": "2026-09-01",
        "pollution_renewal_date": "2026-09-01",
    }
    body.update(over)
    return body


def make_vehicle(admin, cleanup, **over):
    response = admin.post("/masters/vehicles/", json=vehicle_body(**over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/vehicles/{data['id']}")
    return data


def make_trip(admin, cleanup, vehicle_id, route_id, trip_number=1, **over):
    body = {"vehicle_id": vehicle_id, "route_id": route_id, "trip_number": trip_number}
    body.update(over)
    response = admin.post("/masters/trips/", json=body)
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/trips/{data['id']}")
    return data


def pricing_body(vehicle_id, route_id=None, **over):
    body = {
        "vehicle_id": vehicle_id,
        "billing_cycle": "annual",
        "cycle_name": unique("trn_plan_"),
        "amount": "12000.00",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
    }
    if route_id:
        body["route_id"] = route_id
    body.update(over)
    return body


def make_pricing(admin, cleanup, vehicle_id, route_id=None, **over):
    response = admin.post("/masters/transport-pricing/", json=pricing_body(vehicle_id, route_id, **over))
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/masters/transport-pricing/{data['id']}")
    return data


def make_chain(admin, cleanup, fees=1200):
    route = make_route(admin, cleanup)
    stop = make_stop(admin, cleanup, route["id"], 1, fees=fees)
    vehicle = make_vehicle(admin, cleanup)
    trip = make_trip(admin, cleanup, vehicle["id"], route["id"])
    return {"route": route, "stop": stop, "vehicle": vehicle, "trip": trip}


def _drop_student(admin, admission_id, class_id):
    admin.delete(f"/students/admission/{admission_id}")
    admin.delete(f"/masters/class_sections/{class_id}")


def make_student(admin, cleanup, academic_year_id):
    token = unique("trn_")
    response = admin.post(
        "/masters/class_sections/",
        json={"name": token, "academic_year_id": academic_year_id, "short_code": token[:8], "sections": [{"name": "A"}]},
    )
    assert response.status_code == 201, response.text
    klass = response.json()
    section_id = klass["sections"][0]["id"]
    father_email = f"{token}.dad@example.com"
    body = {
        "admission_date": "2026-06-10",
        "admission_number": token,
        "admission_type": "regular",
        "academic_year_id": academic_year_id,
        "admitted_academic_year_id": academic_year_id,
        "admitted_class_id": klass["id"],
        "admitted_section_id": section_id,
        "current_class_id": klass["id"],
        "current_section_id": section_id,
        "address_line1": "1 Test Street",
        "city": "Hyderabad",
        "is_previous_school": False,
        "student": {
            "first_name": token,
            "last_name": "Qa",
            "date_of_birth": "2018-05-05",
            "gender": "Male",
            "is_primary": "not_primary",
            "nationality": "Indian",
            "mother_tongue": "Telugu",
            "primary_phone": "9000100001",
            "father": {
                "name": f"Dad {token}",
                "email": father_email,
                "phone": "9000100002",
                "occupation": "Clerk",
                "gender": "Male",
                "relation_to_student": "Father",
                "salary_range": "1l_3l",
            },
            "mother": {
                "name": f"Mom {token}",
                "email": f"{token}.mom@example.com",
                "phone": "9000100003",
                "occupation": "Nurse",
                "gender": "Female",
                "relation_to_student": "Mother",
                "salary_range": "1l_3l",
            },
        },
    }
    created = admin.post("/students/admission/", json=body)
    if created.status_code != 201:
        admin.delete(f"/masters/class_sections/{klass['id']}")
    assert created.status_code == 201, created.text
    data = created.json()
    cleanup.add(_drop_student, admin, data["id"], klass["id"])
    return {
        "student_id": data["student"]["id"],
        "admission_id": data["id"],
        "admission_number": data["admission_number"],
        "class_id": klass["id"],
        "section_id": section_id,
        "father_email": father_email,
        "academic_year_id": academic_year_id,
    }


def login_created_user(username, default_password):
    anon = Api(tenant_header=QA_TENANT)
    try:
        years = anon.get("/auth/academic-years").json()
        year_id = years[0]["id"]
        first = anon.post(
            "/auth/login", json={"username": username, "password": default_password, "academic_year_id": year_id}
        )
        assert first.status_code == 200, first.text
        new_password = "Qa#" + uuid.uuid4().hex[:12]
        changed = anon.post(
            "/auth/staff/set-password",
            json={
                "change_password_token": first.json()["change_password_token"],
                "new_password": new_password,
                "confirm_password": new_password,
            },
        )
        assert changed.status_code == 200, changed.text
        data = login(username, new_password, QA_TENANT)
        return Api(token=data["access_token"])
    finally:
        anon.close()


def student_client(student):
    return login_created_user(student["admission_number"], "student@123")


def parent_client(student):
    return login_created_user(student["father_email"], "parent@123")


def assign_body(student_id, trip_id, stop_id, **over):
    body = {"student_id": student_id, "trip_id": trip_id, "stop_id": stop_id, "fee_per_term": 1200}
    body.update(over)
    return body


def make_assignment(admin, cleanup, student_id, trip_id, stop_id, **over):
    response = admin.post(
        "/students/student-transport/", json=assign_body(student_id, trip_id, stop_id, **over)
    )
    assert response.status_code == 201, response.text
    data = response.json()
    cleanup.delete_later(admin, f"/students/student-transport/{data['id']}")
    return data
