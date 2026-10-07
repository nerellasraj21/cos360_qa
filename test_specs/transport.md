# Transport (TRN)

Transport covers the school bus operation: routes with their stops, the vehicle fleet, trips (one vehicle on one route with a driver), billing-cycle pricing plans per vehicle, and the assignment of each student to a trip and a pickup stop with a fee per term. Route types and trip types exist as dictionaries in the API only. Staff and admins manage everything on web and mobile; a student or parent sees only their own (or their children's) assignment. The assignment stores a fee but nothing in the fee module reads it, so assigning transport does not bill the student. The legacy `student_trips` table has no API; the screens called "Student Trips" are another view of the student-transport endpoints. This page documents what the code and the running apps do on 2026-10-07; where `docs/modules/transport.md` disagrees with the code, the code wins and the difference is listed under Known gaps.

_Last verified against code: 2026-10-07_

Conventions: test IDs follow `docs/testing/strategy.md` (`TC-TRN-<FF>-<P><NN>`; U unit, A API, E end to end). UI cases (E) use the manual format (Priority P1 smoke, P2 regression, P3 edge). Their preconditions refer to the seeded manual-test tenant `qa_manual` (`backend/scripts/seed_demo_data.py`): routes "Route 1 - Kukatpally" (stops Kukatpally Bus Stand, KPHB Phase 1, JNTU Junction, Moosapet, Demo School Campus) and "Route 2 - Uppal" (Uppal Ring Road, Habsiguda, Tarnaka, Demo School Campus); vehicles School Bus 1 (TS09UA1234, driver Ramesh Yadav) and School Bus 2 (TS09UB5678, driver Mohan Singh), one trip each (trip number 1); four pricing plans (Annual 2026-27 and Monthly 2026-27 for School Bus 1, Annual 2026-27 and Half Yearly 2026-27 for School Bus 2, 2026-06-01 to 2027-03-31); 8 assignments of Class 1 to 5 students (for example Karthik Reddy, Advik Mehta, Saanvi Iyer, Harsha Raju, Tanvi Raju) with fee 4000 (Route 1) or 4667 (Route 2); route types Pickup, Drop and trip types Morning, Evening. Student logins are admission numbers; seeded accounts must change the temporary password at first sign-in. New data a case creates starts with "QA ". Where a UI label or message contains the rupee sign or a dash character it is written here as "Rs" or a hyphen (plain text only), so match by meaning, not by character. Route, route type and trip type create calls are limited to 30 per minute per user.

## Roles

Default grants from `backend/app/service/tenant/permission_catalog.py` (the QA tenant copies `test_tenant_schema`; read the real matrix from the login response before asserting a role):

| Role | Transport grants in the default catalog |
|---|---|
| Admin | `routes`, `route_types`, `route_stops`, `vehicles`, `transport_trips`, `trip_types`, `transport_pricing`, `student_transport`: create, read, update, delete, list. |
| Staff | `routes`, `route_types`, `route_stops`, `vehicles`, `trip_types`: read, list. `transport_trips` and `student_transport`: create, read, update, list. No delete anywhere, no `transport_pricing`. |
| Teacher | `routes`, `route_types`, `route_stops`, `vehicles`, `transport_trips`, `trip_types`: read, list. Nothing for pricing or student transport. |
| Student | `student_transport:read_own` (no endpoint checks this string; the own-record check is by identity). |
| Parent | `student_transport:read_related` (same note). |

The resource for trips is `transport_trips`, not `trips`. Role comparisons for the student-transport read are exact strings (`Student`, `Parent`).

## Feature index

| ID | Title |
|---|---|
| F01 | Transport hubs and navigation |
| F02 | Route types (API only) |
| F03 | Trip types (API only) |
| F04 | Routes |
| F05 | Route stops |
| F06 | Vehicles |
| F07 | Trips |
| F08 | Transport pricing |
| F09 | Student transport assignment (staff and admin) |
| F10 | Student and parent transport view |
| F11 | Student Trips screens and the disabled student_trips API |
| F12 | Transport fee effect |

Menu paths. The Transport menu is tenant data. The QA tenants use the demo catalog (`backend/scripts/seed_demo_catalog.py`), which creates Transport with Routes (`/transport/routes`), Route Stops (`/transport/routeStops`), Vehicles (`/transport/vehicles`), Trips (`/transport/trips`), Pricing (`/transport/pricing`) and puts Student Transport under Students (`/students/studenttransport`). The web sidebar and the Transport and Students hubs hide the names "Route Stops", "Transport Trips" and "Student Transport" (`HIDDEN_MENU_ITEMS` in `web/src/lib/menuUtils.ts`), so those pages are reached from inside the Routes page, the Trips page or by URL. The backend resource names are `routes`, `route_stops`, `vehicles`, `transport_trips`, `transport_pricing`, `student_transport`.

---

## F01 Transport hubs and navigation

**Purpose**: Open the transport area and move to its screens.

**Roles and permissions**: Web hub is built from the user's menu (no permission check beyond the menu). Mobile tab `transport` is visible to every role except student and parent, which get a "My Transport" entry instead; tiles are permission gated.

**Preconditions**: Transport menu seeded for the role (web).

**Steps, web**
1. Click Transport in the sidebar (route `/transport`). Header "Transport Dashboard", subtitle "Manage school transport, routes, vehicles, and student allocations".
2. Under "TRANSPORT SECTIONS" click a card (each has a one-line description, for example "Manage transport routes and their configurations"). Cards come from the children of the Transport menu node minus Route Stops, Transport Trips and Student Transport (for the demo catalog: Routes, Vehicles, Trips, Pricing). A card without a path is dimmed and does nothing.

**Steps, mobile**
1. On the Dashboard tap the "Transport" module (tab screen `/(tabs)/transport`). Banner "Transport Management" with a subtitle listing Routes, Stops, Vehicles, Trips, then "TRANSPORT SECTIONS" with tiles "Routes" ("Manage transport routes and their configurations") and "Vehicles" ("Manage the school vehicle fleet and details"), each enabled only with `list` on `routes` or `vehicles`. These are the only two tiles on the tab.
2. Student and parent roles have no Transport module on the Dashboard and no Transport tab (`hideForRoles`), so the tab's "My Transport" panel ("Transport Information", "View My Transport") is not reachable for them; they open their view from the drawer (Students > Student Transport, mapped to `/transport/student-transport`, F10).
3. A second hub exists at the URL `/transport` (stack route, title "Transport") with stats "Active Routes", "Vehicles", "Students" and a "Manage" list: Routes, Route Stops, Vehicles, Trips, Pricing, Student Transport, Student Trips. It is not linked from the tab; typing `/transport` in Expo web opens this hub, not the tab.

**Expected results**: Navigation only; no data change.

**API endpoints**: The mobile stat strip uses `GET /masters/routes/all_routes`, vehicles and student-transport lists (covered in F04, F06, F09).

**Rules and validations**: Hub card lists depend on the seeded menu; a report or master screen missing from the menu does not appear on the web hub.

**Error and edge cases**: Empty menu: no cards. User without `routes:list`: mobile Routes tile disabled.

**Unit-testable logic**: Web `filterMenuForRole` hidden-name filter; transport hub card filter; mobile tile gating.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-01-U01 | Web `filterMenuForRole` on a Transport node with children Routes, Route Stops, Trips | "Route Stops" removed for every role | passing |
| TC-TRN-01-U02 | Web hub filter on children named Route Stops, Transport Trips, Student Transport, Vehicles | Only Vehicles remains | blocked: hub filter is inline in web/src/routes/_app/transport/index.tsx; needs the helper exported |
| TC-TRN-01-U03 | Mobile tile gating for a user with `routes:list` only | Routes enabled, Vehicles disabled | blocked: tile gating is inline in the mobile transport hub screen; needs the helper exported |
| TC-TRN-01-A01 | Admin `GET /masters/routes/all_routes` and `GET /masters/vehicles/` | Both 200 (the calls behind the mobile stats) | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-01-E01 | P1 | Web | Admin | Seeded tenant qa_manual | 1. Sign in as Admin.<br>2. Click "Transport" in the sidebar (route /transport). | Header "Transport Dashboard" with "Manage school transport, routes, vehicles, and student allocations"; under "TRANSPORT SECTIONS" cards Routes, Vehicles, Trips, Pricing; no card for Route Stops or Student Transport. | passing |
| TC-TRN-01-E02 | P2 | Web | Admin | Seeded tenant qa_manual | 1. Open /transport.<br>2. Click the "Routes" card. | Navigates to /transport/routes (page "Routes"). | planned |
| TC-TRN-01-E03 | P1 | Mobile | Admin | Seeded tenant qa_manual | 1. Sign in as Admin on mobile.<br>2. On the Dashboard tap the "Transport" module (the two tiles show only when you tap the dashboard tile; opening /transport directly shows 7 tiles). | Screen with banner "Transport Management" (subtitle lists Routes, Stops, Vehicles, Trips) and "TRANSPORT SECTIONS" with exactly two tiles: Routes and Vehicles. | passing |
| TC-TRN-01-E04 | P2 | Mobile | Student | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000; first sign-in with the seeded temporary password asks for a new password | 1. Sign in on mobile as student 001.<br>2. Look for a Transport module on the Dashboard.<br>3. Open the drawer and choose Students > Student Transport. | No Transport module or tab for students (only Students, Exam Management, Fee Management); the drawer entry opens "My Transport" (/transport/student-transport) with Karthik's assignment. | planned |
| TC-TRN-01-E05 | P2 | Mobile | Teacher | Seeded tenant qa_manual | 1. Sign in as Teacher on mobile.<br>2. On the Dashboard tap "Transport". | Routes and Vehicles tiles are both enabled (Teacher has list on routes and vehicles). | planned |
| TC-TRN-01-E06 | P3 | Mobile | Admin | Seeded tenant qa_manual | 1. Sign in as Admin on mobile.<br>2. Open /transport (the seven-section Transport hub). | Stack hub "Transport" with stats Active Routes 2, Vehicles 2, Students, and a "Manage" list: Routes, Route Stops, Vehicles, Trips, Pricing, Student Transport, Student Trips (not linked from the Transport module). | planned |

Implemented in (phase 1 unit tests): web/src/__tests__/reports/menu.test.ts and mobile/__tests__/reports/menuUtils.test.ts (the rule exists in both stacks and is tested in both).

---

## F02 Route types (API only)

**Purpose**: A dictionary of route direction names (for example Upward, Downward) meant for dropdowns. No web or mobile screen manages it; a route stores the chosen name as plain text.

**Roles and permissions**: `route_types:create`, `:list` (`/all` and `/dropdown`), `:read` (by id), `:update` (PUT, PATCH), `:delete`. Admin all; Staff and Teacher read and list.

**Preconditions**: Permissions seeded; users must log in again after a seed (clients cache permissions).

**Steps, web**: The feature has no page. The web transport options (`web/src/config/transportOptions.ts`) are a hard-coded Upward and Downward list that is not wired to a screen.

**Steps, mobile**: No screen. `mobile/src/api/transportTypes.ts` has the API wrappers only.

**Expected results**: Rows in `route_types` with unique `type_name`.

**API endpoints**
- `POST /masters/route-types/` body `{type_name, description, is_active}` returns 201.
- `GET /masters/route-types/all` (active only); `GET /masters/route-types/dropdown?active_only=true` returns `[{id, type_name}]`; `GET /masters/route-types/{id}` (inactive allowed).
- `PUT /masters/route-types/{id}` (body as create), `PATCH /masters/route-types/{id}` (partial).
- `DELETE /masters/route-types/{id}` soft-deactivates and returns the row.

**Rules and validations**
- The field is `type_name` (sending `name` gives 422). `type_name` is required (any string; empty string is accepted by the schema).
- Name unique across all rows including inactive ones: 400 "Route type '<name>' already exists". The same check runs on rename.
- The dropdown is cached for 5 minutes per tenant and invalidated on create, update and delete in the same worker. It is ordered by name.
- No foreign key from routes: renaming or deleting a type never changes existing routes.

**Error and edge cases**: Unknown id 404 "Route type not found"; malformed id 422; `Staff` write attempts 403.

**Unit-testable logic**: Duplicate-name guards on create, PUT and PATCH; soft delete; dropdown projection and ordering; cache invalidation key.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-02-U01 | `add_route_type` with an existing name (active or inactive) | HTTPException 400 "Route type '<name>' already exists" | passing |
| TC-TRN-02-U02 | `update_partial_details_route_type` with `type_name` equal to the current name | No duplicate error | passing |
| TC-TRN-02-U03 | `update_partial_details_route_type` with only `description` | `type_name` unchanged (`exclude_unset`) | passing |
| TC-TRN-02-U04 | `deactivate_route_type` | `is_active=False` and the dropdown cache entry invalidated | passing |
| TC-TRN-02-A01 | Admin `POST /masters/route-types/` `{type_name:"QA Upward"}` | 201 with id, `is_active=true`, created_at, updated_at | passing |
| TC-TRN-02-A02 | Create with `{name:"X"}` | 422 (field is `type_name`) | passing |
| TC-TRN-02-A03 | Create the same `type_name` twice | Second call 400 | passing |
| TC-TRN-02-A04 | `GET /masters/route-types/all` after deactivating one | Inactive excluded | passing |
| TC-TRN-02-A05 | `GET /masters/route-types/dropdown` and `?active_only=false` | `[{id, type_name}]` ordered by name; inactive only with false | passing |
| TC-TRN-02-A06 | `GET /masters/route-types/{id}` existing, inactive, unknown, malformed | 200, 200, 404 "Route type not found", 422 | passing |
| TC-TRN-02-A07 | `PUT` full body with a new name; `PUT` clashing with another name | 200; 400 | passing |
| TC-TRN-02-A08 | `PATCH` description only | 200; name unchanged | passing |
| TC-TRN-02-A09 | `DELETE` then `GET /all` | 200 with `is_active=false`; absent from `/all` | passing |
| TC-TRN-02-A10 | Reusing the name of a deleted type | 400 (inactive rows count) | passing |
| TC-TRN-02-A11 | Role matrix | Admin 2xx on all; Staff and Teacher 200 on GET `/all`, `/dropdown`, `/{id}` and 403 on POST, PUT, PATCH, DELETE; Student, Parent 403 | passing |
| TC-TRN-02-A12 | Tenant isolation | A type from tenant A is absent from tenant B's `/all` and dropdown; same name can exist in both | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-02-E01 | P1 | Web | Admin | Seeded tenant qa_manual (route types Pickup and Drop exist in the API) | 1. Open Transport > Routes.<br>2. Click "Add Route" and read the dialog.<br>3. Close it; on mobile open the Routes screen and tap "Add Route". | Neither form has a route type or trip type control; the seeded routes still store route_type Pickup as plain text (documents the absence). | passing |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F03 Trip types (API only)

**Purpose**: A dictionary of trip names (for example First Trip, Second Trip). Like route types it has no screen.

**Roles and permissions**: `trip_types:create`, `:list`, `:read`, `:update`, `:delete`. Admin all; Staff and Teacher read and list.

**Preconditions**: As F02.

**Steps, web**: No page. Web transport options hard-code "first trip" and "second trip".

**Steps, mobile**: No screen.

**Expected results**: Rows in `trip_types` with unique `type_name`.

**API endpoints**
- `POST /masters/trip-types/` returns 200 (no 201 status is declared).
- `GET /masters/trip-types/all`; `GET /masters/trip-types/dropdown?active_only=true`; `GET /masters/trip-types/{id}`.
- `PUT /masters/trip-types/{id}`; `PATCH /masters/trip-types/{id}`.
- `DELETE /masters/trip-types/{id}` returns `{"message": "Trip type soft deleted"}`.

**Rules and validations**: Same as route types (unique `type_name` including inactive rows, 5-minute dropdown cache, no foreign key to trips or routes), with these differences: create returns 200 and delete returns a message, not the row.

**Error and edge cases**: Unknown id 404 "Trip type not found".

**Unit-testable logic**: Duplicate guards; soft delete message; dropdown projection.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-03-U01 | `add_trip_type` with an existing name | HTTPException 400 with the trip type name | passing |
| TC-TRN-03-U02 | Soft delete service return value | `{"message": "Trip type soft deleted"}` | passing |
| TC-TRN-03-A01 | Admin `POST /masters/trip-types/` `{type_name:"QA First Trip"}` | 200 (not 201) with id and `is_active=true` | passing |
| TC-TRN-03-A02 | Duplicate create; create with `{name:"X"}` | 400; 422 | passing |
| TC-TRN-03-A03 | `GET /all` and `GET /dropdown` | Active only; dropdown `[{id, type_name}]` ordered by name | passing |
| TC-TRN-03-A04 | `GET /{id}` existing, unknown, malformed | 200; 404; 422 | passing |
| TC-TRN-03-A05 | `PUT` rename; `PUT` to an existing name | 200; 400 | passing |
| TC-TRN-03-A06 | `PATCH` description only | 200; name unchanged | passing |
| TC-TRN-03-A07 | `DELETE` | 200 `{"message":"Trip type soft deleted"}`; gone from `/all` | passing |
| TC-TRN-03-A08 | Role matrix | Admin 2xx; Staff, Teacher 200 on reads and 403 on writes; Student, Parent 403 | passing |
| TC-TRN-03-A09 | Tenant isolation | Tenant B cannot see tenant A's trip types | passing |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F04 Routes

**Purpose**: Define a bus route: name, start and end point, number of stops, daily start and end times, and whether it is active.

**Roles and permissions**: `routes:create`, `:list` (`/all_routes`, `/dropdown`), `:read` (`/routeid/{id}`, `/stops-by-route`), `:update` (PUT, PATCH), `:delete`. Admin all; Staff and Teacher read and list. Web page guard `routes:list`.

**Preconditions**: None (route types are optional free text).

**Steps, web**
1. Open `/transport/routes` (Transport > Routes). The table "Routes" has columns S.No., Route Name, Starting Point, Ending Point, Number of Stops, Up Journey Time, Down Journey Time, Active, Stops ("View" button) and Actions (pencil "Edit" for inline editing, trash "Delete"); "Export", search "Search..." and pagination ("Rows per page" 5 to 100) surround it. Delete asks "Delete Row?" ("Are you sure you want to delete this row? This action cannot be undone.") and toasts "Route deleted successfully!".
2. Click "Add Route". Dialog "Add New Route": "Route Name *" (placeholder "Enter route name"), "Starting Point *", "Ending Point *", "Number of Stops" (number, min 0), "Active". Under "Route Stops (auto-filled from "Number of Stops")" a row appears per stop with "Stop Name", "Amount (Rs/yr)", "Up Journey Time", "Down Journey Time" (defaults 07:00 AM and 08:30 AM) and "Remove" (removing a row lowers Number of Stops). With 0 stops it says "Enter a number in "Number of Stops" to add stop rows." Buttons "Cancel" and "Add Route".
3. Submitting creates the route (with daily times fixed at 07:00:00 to 08:30:00, since the dialog has no inputs for them) and then one stop per named row with numbers 1, 2, 3 in order; rows left without a name create no stop. Toast "Route "<name>" created successfully!"; a duplicate name gives "Failed to create route: Route '<name>' already exists".
4. Edit a route inline in the table; the delete action deactivates it. Click "View" to scroll to the Route Stops manager (F05). Route type and trip type are not shown anywhere.

**Steps, mobile**
1. Dashboard "Transport" module, "Routes" tile, screen "Routes". Cards show the route, "<start> -> <end>" with an arrow, the times, "Number of Stops" and "View Stops". Search "Search routes...", "Export" (Export As: "Export to CSV", "Export to Excel", "Download Data"). "Add Route" opens "Add New Route": "Route Name *", "Starting Point *", "Ending Point *", "Number of Stops", "Active" and "Route Stops" rows auto-filled from Number of Stops (as on web; no journey time inputs), "Cancel", "Add Route". Messages: "Route name is required", success "Route created successfully", "Route updated successfully", "Route deleted successfully"; delete confirm title "Delete Route".
2. A "Route Stops" footer ("Route Name:" picker, "Add Stop") manages stops (F05).

**Expected results**: A `routes` row, unique by `route_name`. Deleting sets `is_active=false` and removes it from `/all_routes`, the dropdown and the routes list; its stops stay active.

**API endpoints**
- `POST /masters/routes/` body `{route_name, starting_stop, ending_stop, number_of_stops, route_type, trip_type, start_time, end_time, is_active}` returns 201.
- `GET /masters/routes/all_routes` (active only); `GET /masters/routes/routeid/{id}` (any state); `GET /masters/routes/dropdown?active_only=true` returns `[{id, route_name}]`; `GET /masters/routes/stops-by-route?route_name=` returns the route's stops (all, including inactive).
- `PUT /masters/routes/{id}` (full body), `PATCH /masters/routes/{id}` (partial), `DELETE /masters/routes/{id}` (deactivate, returns the row).

**Rules and validations**
- Required: `route_name`, `starting_stop`, `ending_stop`, `number_of_stops` (int), `start_time`, `end_time` (time `HH:MM[:SS]`). `route_type` and `trip_type` are optional strings with no foreign key. No check that `end_time` is after `start_time` and no check that `number_of_stops` equals the stop count.
- `route_name` unique across all rows including inactive: 400 "Route '<name>' already exists" (also on rename).
- Dropdown cached 5 minutes per tenant; invalidated on create only, so a rename or deactivation can leave the dropdown stale for up to 5 minutes.
- Delete does not check trips, stops or assignments.

**Error and edge cases**: Unknown id 404 "Route not found"; `stops-by-route` with an unknown name 404 "Route not found"; missing `route_name` query 422.

**Unit-testable logic**: Duplicate-name guard (create, PUT, PATCH); soft delete; dropdown cache invalidation (create only); web stop-row generation from "Number of Stops" (resize up or down, remove lowers the count).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-04-U01 | `add_route` with an existing name | HTTPException 400 "Route '<name>' already exists" | passing |
| TC-TRN-04-U02 | `update_partial_details_route` with the same name | No duplicate error | passing |
| TC-TRN-04-U03 | `deactivate_route` | `is_active=False`; no stop or trip touched | passing |
| TC-TRN-04-U04 | `RouteCreate` with `start_time="25:00"` | ValidationError | passing |
| TC-TRN-04-U05 | `RouteCreate` with `end_time` earlier than `start_time` | Accepted (no ordering rule) | passing |
| TC-TRN-04-U06 | Cache invalidation: after `add_route`, then after `deactivate_route` | Dropdown cache cleared on create only | passing |
| TC-TRN-04-U07 | Web stop-row generation: Number of Stops 3 then 2 then remove one row | 3 rows, 2 rows, then 1 row with Number of Stops 1 | blocked: stop-row generation is inline in web/src/pages/transport/routes.tsx; needs the helper exported |
| TC-TRN-04-A01 | Admin `POST /masters/routes/` `{route_name:"QA Route 1", starting_stop:"School", ending_stop:"Market", number_of_stops:3, start_time:"07:00:00", end_time:"08:30:00"}` | 201; `is_active=true`; times echoed; `route_type` null | passing |
| TC-TRN-04-A02 | Create with `route_type:"Upward"` and `trip_type:"First Trip"` | 201; stored as given text | passing |
| TC-TRN-04-A03 | Duplicate `route_name` | 400 "Route 'QA Route 1' already exists" | passing |
| TC-TRN-04-A04 | Missing `route_name`, `start_time` or `number_of_stops`; `number_of_stops:"abc"` | 422 | passing |
| TC-TRN-04-A05 | `GET /masters/routes/all_routes` after deactivating one | Inactive excluded | passing |
| TC-TRN-04-A06 | `GET /masters/routes/routeid/{id}` for active, inactive, unknown, malformed | 200, 200, 404 "Route not found", 422 | passing |
| TC-TRN-04-A07 | `GET /masters/routes/dropdown` and `?active_only=false` | `[{id, route_name}]` ordered by name | passing |
| TC-TRN-04-A08 | Create route then immediately rename it, then dropdown | Dropdown may still show the old name (cache); documents the stale window | passing |
| TC-TRN-04-A09 | `GET /masters/routes/stops-by-route?route_name=QA Route 1` with two stops | Both stops (ordered as stored) | passing |
| TC-TRN-04-A10 | `stops-by-route` with an unknown name; with no parameter | 404; 422 | passing |
| TC-TRN-04-A11 | `PUT` with a new name; `PUT` clashing name | 200; 400 | passing |
| TC-TRN-04-A12 | `PATCH {"is_active": false}` | 200; route disappears from `/all_routes` | passing |
| TC-TRN-04-A13 | `DELETE` a route that has stops and a trip | 200 `is_active=false`; stops remain active; the trip remains | passing |
| TC-TRN-04-A14 | Reuse the name of a deleted route | 400 (inactive rows count) | passing |
| TC-TRN-04-A15 | Role matrix | Admin 2xx; Staff and Teacher 200 on GET endpoints and 403 on POST, PUT, PATCH, DELETE; Student, Parent 403 | passing |
| TC-TRN-04-A16 | Tenant isolation | Tenant B cannot see, and may reuse, tenant A's route names; by id 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-04-E01 | P1 | Web | Admin | Seeded tenant qa_manual | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Click "Add Route".<br>3. Enter Route Name "QA Route 3 - Ameerpet", Starting Point "QA Ameerpet", Ending Point "Demo School Campus", Number of Stops 2.<br>4. In the two stop rows enter Stop Name "QA Stop A" and "QA Stop B".<br>5. Click "Add Route".<br>6. Click "View" on the new row. | Toast "Route "QA Route 3 - Ameerpet" created successfully!"; the row shows Up 07:00 and Down 08:30; the Route Stops manager lists QA Stop A (1) and QA Stop B (2). | passing |
| TC-TRN-04-E02 | P2 | Web | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Click "Add Route".<br>3. Enter Route Name "Route 1 - Kukatpally", Starting Point "QA X", Ending Point "QA Y".<br>4. Click "Add Route". | Toast "Failed to create route: Route 'Route 1 - Kukatpally' already exists"; no second row. | planned |
| TC-TRN-04-E03 | P2 | Web | Admin | Route "QA Route 3 - Ameerpet" exists (TC-TRN-04-E01 done) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Click the pencil (Edit) icon in its row.<br>3. Change Ending Point to "QA Campus Gate".<br>4. Save the row. | Toast "Route "QA Route 3 - Ameerpet" updated successfully!"; the row shows QA Campus Gate. | planned |
| TC-TRN-04-E04 | P2 | Web | Admin | Route "QA Route 3 - Ameerpet" exists (TC-TRN-04-E01 done) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Click the trash (Delete) icon in its row.<br>3. In "Delete Row?" click "Delete". | Confirm text "Are you sure you want to delete this row? This action cannot be undone."; toast "Route deleted successfully!"; the row leaves the table (stored is_active false). | planned |
| TC-TRN-04-E05 | P3 | Web | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus); Seeded route "Route 2 - Uppal" (4 stops) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Type "Uppal" in "Search...". | Only Route 2 - Uppal remains. | planned |
| TC-TRN-04-E06 | P2 | Web | Teacher | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Sign in as Teacher.<br>2. Click "Transport" in the sidebar, then "Routes". | Routes table visible with "Export" and "View"; no "Add Route", Edit or Delete controls; the stops manager has no "Add Stop". | planned |
| TC-TRN-04-E07 | P1 | Mobile | Admin | Seeded tenant qa_manual | 1. Sign in as Admin on mobile.<br>2. Dashboard > "Transport" > "Routes".<br>3. Tap "Add Route".<br>4. Enter Route Name "QA Route 4 - Miyapur", Starting Point "QA Miyapur", Ending Point "Demo School Campus".<br>5. Tap "Add Route". | Toast "Route created successfully"; the card "QA Route 4 - Miyapur" appears (the form has no journey time fields, so times use the defaults). | passing |
| TC-TRN-04-E08 | P3 | Mobile | Admin | Seeded tenant qa_manual | 1. Open the mobile Routes screen.<br>2. Tap "Add Route".<br>3. Leave Route Name empty and tap "Add Route". | Toast "Error" with "Route name is required". | planned |
| TC-TRN-04-E09 | P3 | Mobile | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Open the mobile Routes screen.<br>2. Tap "Export".<br>3. Choose "Export to CSV". | A CSV containing Route 1 - Kukatpally and Route 2 - Uppal is shared or downloaded; no "Failed to export CSV" toast. | planned |
| TC-TRN-04-E10 | P2 | Mobile | Admin | Route "QA Route 4 - Miyapur" exists (TC-TRN-04-E07 done) | 1. Open the mobile Routes screen.<br>2. Delete "QA Route 4 - Miyapur" and confirm "Delete Route". | Toast "Route deleted successfully"; the card disappears. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F05 Route stops

**Purpose**: Define the ordered pickup and drop stops of a route with timings and a default fee.

**Roles and permissions**: `route_stops:create`, `:list` (`GET /`), `:read` (by id), `:update` (PUT, PATCH), `:delete`. Admin all; Staff and Teacher read and list.

**Preconditions**: An active route (F04).

**Steps, web**
1. On `/transport/routes` use the "Route Stops" manager below the table: "Route Name:" dropdown ("Select a route to view stops..."); table columns S.No., Stop Name, Amount (Rs/yr), Up Journey Time, Down Journey Time, Actions.
2. "Add Stop" (needs `route_stops:create`, enabled once a route is selected) opens "Add Stop": "Stop Name *", "Stop Number *" (defaults to existing stops plus one), "Amount (Rs/yr)", "Up Journey Time *" ("Select time"), "Down Journey Time", "Active", buttons "Cancel" and "Add Stop". The request also sends `reaching_time` equal to the up time (or 00:00:00). The up time is not enforced: a stop saved without it shows dashes for the times (seen 2026-10-07). Toast "Route stop "<name>" created successfully!"; with no stops the manager says "No stops for this route.", before choosing a route "Select a route to view its stops."
3. Edit pencil (title "Edit") makes the row editable (name, amount, up and down time); the trash (title "Delete") opens "Delete Stop" (Are you sure you want to delete the stop "<name>"? This action cannot be undone.); toast "Route stop deleted successfully!".
4. The standalone `/transport/routeStops` page (hidden from menus) is a table with columns S.No., Route, Stop Name, Stop Number, Pickup Time, Drop Time, Active, Actions ("Export", "Add Route Stop"); a stop whose route is inactive shows the raw route id in the Route column. Its add form has with Route, Stop Name, Stop Number, Reaching Time, Pickup Time, Drop Time, Active.

**Steps, mobile**
1. Reached from the routes screen footer ("Route Stops", "Route Name:", "Add Stop") or the `/transport` stack hub ("Route Stops"): screen "Route Stops", "Filter by Route:" ("Select a route to view stops..."; until then "No Route Stops Found"), search "Search stops...", "Add Stop" with "Stop Name *" (placeholder "Enter stop name"), "Stop Number *" (placeholder "1"), "Up Journey Time *", "Down Journey Time", "Active". Messages: "Route is required", "Stop name is required", "Stop Created", "Stop Updated", "Stop Deleted"; confirm title "Delete Route Stop".

**Expected results**: A `route_stops` row. Stop numbers are unique per route including inactive stops (a deactivated stop's number cannot be reused). Delete deactivates and hides it from lists.

**API endpoints**
- `POST /masters/route-stops/` body `{route_id, name, number, reaching_time (required), pickup_time, drop_time, fees, is_active}` returns 201 with `route_name`.
- `GET /masters/route-stops/` returns all active stops of all routes; it ignores any query parameter. `GET /masters/route-stops/{id}`.
- `PUT /masters/route-stops/{id}` (full body), `PATCH /masters/route-stops/{id}` (partial), `DELETE /masters/route-stops/{id}` (deactivate).
- `GET /masters/vehicles/{vehicle_id}/routes/{route_id}/stops` lists a route's active stops for a vehicle (F06).
- `GET /masters/routes/stops-by-route?route_name=` (F04).

**Rules and validations**
- `route_id`, `name`, `number` and `reaching_time` are required even though `reaching_time` is deprecated; `pickup_time` and `drop_time` are optional and must come back in every response.
- (`route_id`, `number`) unique: 400 "Stop number <n> already exists on this route" on create, PUT and PATCH (when route or number changes).
- `fees` is a float in the schema but an `Integer` column: send whole numbers (a fraction such as 25.5 fails in the database).
- The route id is not validated on create; an unknown route id fails as a database error.
- `GET /` is not filtered by route; clients filter by `route_id` in the browser.

**Error and edge cases**: Unknown id 404 "Route stop not found". Whole-route stop lists on web and mobile assignment screens show stops of every route (see F09).

**Unit-testable logic**: Duplicate (route, number) guard on create, PUT and PATCH; response dict builder includes `pickup_time`, `drop_time`, `route_name`; soft delete; web default stop number and time padding (`HH:MM` to `HH:MM:00`).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-05-U01 | `add_route_stop` where (route, number) exists | HTTPException 400 "Stop number 1 already exists on this route" | passing |
| TC-TRN-05-U02 | `update_partial_details_route_stop` changing number to one used by another stop on the route | 400 | passing |
| TC-TRN-05-U03 | `update_partial_details_route_stop` with only `name` | No uniqueness query; fields otherwise unchanged | passing |
| TC-TRN-05-U04 | Response dict of `get_route_stops` | Contains `pickup_time`, `drop_time`, `fees`, `route_name` for every item | passing |
| TC-TRN-05-U05 | `RouteStopCreate` without `reaching_time` | ValidationError | passing |
| TC-TRN-05-U06 | Web time padding for "07:05" and "07:05:00" | "07:05:00" for both | blocked: time padding is inline in web/src/pages/transport/routeStops.tsx; needs the helper exported |
| TC-TRN-05-U07 | Web default number for a route with 4 stops | "5" | blocked: default stop number is inline in web/src/pages/transport/routeStops.tsx; needs the helper exported |
| TC-TRN-05-A01 | Admin `POST /masters/route-stops/` route R, name "Stop A", number 1, reaching_time "07:10:00", pickup_time "07:10:00", drop_time "08:20:00", fees 1200 | 201; response has `route_name`, `fees=1200.0`, `pickup_time` and `drop_time` echoed | passing |
| TC-TRN-05-A02 | Create (R, number 1) again | 400 "Stop number 1 already exists on this route" | passing |
| TC-TRN-05-A03 | Create number 1 on a different route | 201 | passing |
| TC-TRN-05-A04 | Create without `reaching_time`; without `route_id`; `number:"x"` | 422 | passing |
| TC-TRN-05-A05 | Create with an unknown `route_id` | Non-2xx database error response (no 201) | passing |
| TC-TRN-05-A06 | Create with `fees:25.5` | Not 2xx (integer column); documents the limitation | passing |
| TC-TRN-05-A07 | `GET /masters/route-stops/` with stops on two routes and `?route_id=<R>` | Returns all active stops of both routes (parameter ignored) | passing |
| TC-TRN-05-A08 | `GET /masters/route-stops/{id}` existing, unknown, malformed | 200 with `route_name`; 404 "Route stop not found"; 422 | passing |
| TC-TRN-05-A09 | `PUT` full body changing name and times | 200; fields updated | passing |
| TC-TRN-05-A10 | `PATCH {"number": 2}` clashing with another stop | 400 | passing |
| TC-TRN-05-A11 | `PATCH {"drop_time":"08:45:00"}` then GET | `drop_time` persisted and returned | passing |
| TC-TRN-05-A12 | `DELETE` a stop then `GET /` | 200 `is_active=false`; absent from the list | passing |
| TC-TRN-05-A13 | Recreate (R, number 1) after deleting that stop | 400 (inactive rows keep the number) | passing |
| TC-TRN-05-A14 | Role matrix | Admin 2xx; Staff and Teacher 200 on GETs and 403 on POST, PUT, PATCH, DELETE; Student, Parent 403 | passing |
| TC-TRN-05-A15 | Tenant isolation | Tenant B list and by-id exclude tenant A's stops | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-05-E01 | P1 | Web | Admin | Seeded route "Route 2 - Uppal" (4 stops) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. In "Route Name:" choose "Route 2 - Uppal".<br>3. Click "Add Stop".<br>4. Enter Stop Name "QA Stop Nagole", set a free Stop Number (a soft-deleted stop keeps its number, unique per route including inactive stops, so 5 may be taken), Amount (Rs/yr) 1400, Up Journey Time 07:50.<br>5. Click "Add Stop". | Toast "Route stop "QA Stop Nagole" created successfully!"; the row shows the chosen stop number, amount Rs 1,400 and 07:50. | passing |
| TC-TRN-05-E02 | P2 | Web | Admin | Seeded route "Route 2 - Uppal" (4 stops) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Choose "Route 2 - Uppal" in "Route Name:".<br>3. Click "Add Stop", enter Stop Name "QA Dup Stop", Stop Number 1.<br>4. Click "Add Stop". | Toast "Failed to create route stop: Stop number 1 already exists on this route"; no new row. | planned |
| TC-TRN-05-E03 | P2 | Web | Admin | Stop "QA Stop Nagole" exists (TC-TRN-05-E01 done) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Choose "Route 2 - Uppal".<br>3. Click the pencil (title Edit) on "QA Stop Nagole".<br>4. Change Amount to 1450 and Down Journey Time to 17:00, then save. | Toast "Route stop "QA Stop Nagole" updated successfully!"; the row shows Rs 1,450 and 17:00. | planned |
| TC-TRN-05-E04 | P2 | Web | Admin | Stop "QA Stop Nagole" exists (TC-TRN-05-E01 done) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Choose "Route 2 - Uppal".<br>3. Click the trash (title Delete) on "QA Stop Nagole".<br>4. In "Delete Stop" click "Delete". | Confirm text Are you sure you want to delete the stop "QA Stop Nagole"? This action cannot be undone.; toast "Route stop deleted successfully!"; the row disappears. | planned |
| TC-TRN-05-E05 | P2 | Web | Teacher | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Sign in as Teacher.<br>2. Click "Transport" in the sidebar, then "Routes".<br>3. Choose "Route 1 - Kukatpally" in "Route Name:". | The five stops are listed; no "Add Stop", Edit or Delete controls. | planned |
| TC-TRN-05-E06 | P3 | Mobile | Admin | Seeded tenant qa_manual | 1. Sign in as Admin on mobile.<br>2. Open /transport (the seven-section Transport hub).<br>3. Tap "Route Stops".<br>4. Without choosing a route in "Filter by Route:" tap "Add Stop" and save. | Toast "Error" with "Route is required" (the screen shows "No Route Stops Found" until a route is chosen). | planned |
| TC-TRN-05-E07 | P2 | Mobile | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Open Route Stops on mobile.<br>2. Choose "Route 1 - Kukatpally" in "Filter by Route:".<br>3. Tap "Add Stop": Stop Name "QA Stop Allwyn", Stop Number 6, Up Journey Time 07:40.<br>4. Save. | Toast "Stop Created" with "Route stop created successfully"; the stop appears in the list. | planned |
| TC-TRN-05-E08 | P2 | Mobile | Admin | Stop "QA Stop Allwyn" exists (TC-TRN-05-E07 done) | 1. Open Route Stops on mobile and choose Route 1 - Kukatpally.<br>2. Delete "QA Stop Allwyn" and confirm "Delete Route Stop". | Toast "Stop Deleted" with "Route stop deleted successfully"; the stop disappears. | planned |
| TC-TRN-05-E09 | P3 | Web | Admin | Seeded route "Route 2 - Uppal" (4 stops) | 1. Click "Transport" in the sidebar, then "Routes".<br>2. Choose "Route 2 - Uppal".<br>3. Click "Add Stop", enter only Stop Name "QA No Time" (Stop Number prefilled).<br>4. Click "Add Stop". | Expected: "Up Journey Time *" is enforced. Today the stop is saved without times (shown as a dash) and reaching_time is stored as 00:00:00 (Known gaps 20). Delete the stop afterwards. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F06 Vehicles

**Purpose**: Register school vehicles (bus, van, auto) with registration, driver, licence and insurance details, and attach them to routes through trips.

**Roles and permissions**: `vehicles:create`, `:list` (`GET /`, `/dropdown`), `:read` (by id and the three sub-resources), `:update` (PUT, PATCH), `:delete`. Admin all; Staff and Teacher read and list.

**Preconditions**: For the trip rows in the add dialog: routes (F04) and drivers (staff with a user account).

**Steps, web**
1. Open `/transport/vehicles` (title "Vehicles"). Columns S.No., Vehicle Name, Reg. Number, Driver, Co-Driver, Licence No., Licence Expiry, Insurance Vendor, Insurance Expiry, Trips, Active, Edit (pencil), Actions (trash "Delete", confirm "Delete Row?", toast "Vehicle deleted successfully"). Below the table "Vehicle:" ("Type to search vehicle...") shows the chosen vehicle's trips ("Select a vehicle to view its trips.").
2. "Add Vehicle" opens "Add Vehicle": "Vehicle Name *" (placeholder "Bus 01"), "Registration Number *" (placeholder "KA01AB1234"), "Fee Category", "Fee Type", "Driving Licence No. *", "Driver Name" ("Select driver..."), "Co-Driver Name", "Driving Licence Expiry Date", "Bus Insurance Vendor", "Number of Trips", "Fees", "Insurance Expiry Date", "Active", and a "Trips" section that starts with two rows (Trip 1, Trip 2; "Type to search route...", "Select driver...") plus "Add Trip". Submit button "Add Vehicle". Validation toasts: "Vehicle Name and Registration Number are required", "Driving Licence No. is required", "Driving Licence No. cannot exceed <n> characters".
3. Submit runs three requests: create with core fields (vehicle type fixed to "Bus", inspection and pollution dates set to today), a PUT with the extended fields (fee category and fee type are sent but dropped by the API), then one trip per row that has both a route and a driver, with trip numbers 1, 2, 3. Toasts "Vehicle created successfully" and "Vehicle updated successfully" (seen 2026-10-07). The "Edit" column opens an edit dialog of the same fields.

**Steps, mobile**
1. Dashboard "Transport" module, "Vehicles" tile, screen "Vehicles", search "Search vehicles...", a "Vehicle Trips" panel ("Select vehicle") below the list; empty list "No Vehicles Found" ("Add your first vehicle to get started"). "Add Vehicle": "Vehicle Name *" (placeholder "Enter vehicle name"), "Registration Number *" (placeholder "e.g. AP09AB1234"), "Fee Category", "Fee Type", "Driving Licence No. *" (placeholder "Enter licence number"), "Driver Name", "Co-Driver Name", "Driving Licence Expiry Date", "Bus Insurance Vendor" (placeholder "Enter vendor name"), "Number of Trips" (placeholder "e.g. 2"), "Fees (Rs)" (placeholder "e.g. 1200"), "Insurance Expiry Date", "Active", and "Trips" (Trip 1, Trip 2 with Route and Driver, plus "Add Trip"); submit "Add Vehicle". Same validation messages as web; success "Vehicle created successfully", "Vehicle updated successfully", "Vehicle deleted successfully".

**Expected results**: A `vehicles` row (unique registration number) plus optional trips. Delete deactivates the vehicle only; its trips remain.

**API endpoints**
- `POST /masters/vehicles/` body `{name, registration_number, vehicle_type, last_inspected_date, pollution_renewal_date, fees, driver_name, co_driver_name, driving_licence_no, driving_licence_exp_date, bus_insurance_vendor, number_of_trips, insurance_expiry_date, is_ac, is_active}` returns 201.
- `GET /masters/vehicles/` (active only); `GET /masters/vehicles/dropdown?active_only=true` returns `[{id, name}]` (not cached, not ordered); `GET /masters/vehicles/{id}`.
- `GET /masters/vehicles/{id}/routes` returns active routes that have a trip with the vehicle; `GET /masters/vehicles/{id}/trips` returns `[{id, trip_number, route_id, route_name}]`; `GET /masters/vehicles/{id}/routes/{route_id}/stops` returns the route's active stops ordered by number, or 404 "Vehicle is not assigned to this route".
- `PUT /masters/vehicles/{id}` (full body), `PATCH /masters/vehicles/{id}`, `DELETE /masters/vehicles/{id}` (deactivate).

**Rules and validations**
- Required on create: `name`, `registration_number`, `vehicle_type` (free text such as Bus, Van, Auto), `last_inspected_date`, `pollution_renewal_date`. The web and mobile screens additionally require the licence number.
- `registration_number` unique including inactive vehicles: 400 "Vehicle '<reg>' already registered" (also on PUT and PATCH).
- `fees` is stored as `Numeric(10,2)`. `fee_category_id` and `fee_type_id` do not exist in the API schema and are dropped silently.
- The vehicle dropdown is not cached (the module doc says it is).

**Error and edge cases**: Unknown id 404 "Vehicle not found"; the sub-resource endpoints return `[]` for a vehicle without trips (no 404 for an unknown vehicle id on `/routes` and `/trips`).

**Unit-testable logic**: Duplicate registration guard (create, PUT, PATCH); soft delete; `get_vehicle_route_stops` assignment check and ordering; dropdown projection; web three-step create orchestration (core, PATCH, trips with `i+1` numbering).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-06-U01 | `add_vehicle` with an existing registration number | HTTPException 400 "Vehicle 'KA01AB1234' already registered" | passing |
| TC-TRN-06-U02 | `update_partial_details_vehicle` with the same registration number | No duplicate error | passing |
| TC-TRN-06-U03 | `get_vehicle_route_stops` when no trip links the vehicle and route | HTTPException 404 "Vehicle is not assigned to this route" | passing |
| TC-TRN-06-U04 | `get_vehicle_route_stops` with stops numbered 3, 1, 2 (one inactive) | Active stops ordered 1, 2 or 1, 3 by number | passing |
| TC-TRN-06-U05 | `VehicleCreate` without `last_inspected_date` | ValidationError | passing |
| TC-TRN-06-U06 | Web create orchestration with two valid trip rows and one row missing a driver | Two trips created with `trip_number` 1 and 2 | blocked: three-step create orchestration is inline in web/src/pages/transport/vehicles.tsx; needs the helper exported |
| TC-TRN-06-A01 | Admin `POST /masters/vehicles/` name "QA Bus 1", registration "QA01AB0001", type "Bus", inspection and pollution dates "2026-09-01" | 201; `is_active=true`; dates echoed | passing |
| TC-TRN-06-A02 | Create with the extended fields (`driver_name`, `driving_licence_no`, `fees:1200.50`, `is_ac:true`, `number_of_trips:2`) | 201; all echoed; `fees` as a number | passing |
| TC-TRN-06-A03 | Duplicate registration number | 400 "Vehicle 'QA01AB0001' already registered" | passing |
| TC-TRN-06-A04 | Create with `fee_category_id` and `fee_type_id` extra fields | 201; the fields are not in the response (silently dropped) | passing |
| TC-TRN-06-A05 | Create without `name`; without `vehicle_type`; invalid date text | 422 | passing |
| TC-TRN-06-A06 | `GET /masters/vehicles/` after deactivating one | Inactive excluded | passing |
| TC-TRN-06-A07 | `GET /masters/vehicles/dropdown` and `?active_only=false` | `[{id, name}]`; inactive only with false | passing |
| TC-TRN-06-A08 | `GET /masters/vehicles/{id}` existing, inactive, unknown, malformed | 200, 200, 404 "Vehicle not found", 422 | passing |
| TC-TRN-06-A09 | Vehicle with two trips: `GET /{id}/routes` and `GET /{id}/trips` | Routes `[{id, route_name}]` distinct and ordered by name; trips `[{id, trip_number, route_id, route_name}]` ordered by `trip_number` | passing |
| TC-TRN-06-A10 | `GET /{id}/routes/{route_id}/stops` for an assigned route | Active stops ordered by `number` with `pickup_time`, `drop_time`, `fees` | passing |
| TC-TRN-06-A11 | `GET /{id}/routes/{route_id}/stops` for an unassigned route | 404 "Vehicle is not assigned to this route" | passing |
| TC-TRN-06-A12 | `GET /{id}/routes` and `/trips` for a vehicle with no trips | 200 `[]` | passing |
| TC-TRN-06-A13 | `PUT` full body; `PUT` clashing registration | 200; 400 | passing |
| TC-TRN-06-A14 | `PATCH {"driver_name":"R. Kumar","is_active":false}` | 200; vehicle leaves the list | passing |
| TC-TRN-06-A15 | `DELETE` a vehicle that has a trip | 200 `is_active=false`; the trip still exists | passing |
| TC-TRN-06-A16 | Role matrix | Admin 2xx on all; Staff and Teacher 200 on the GET endpoints (including sub-resources) and 403 on POST, PUT, PATCH, DELETE; Student, Parent 403 | passing |
| TC-TRN-06-A17 | Tenant isolation | Tenant B cannot see tenant A's vehicles; sub-resources return `[]` or 404 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-06-E01 | P1 | Web | Admin | Seeded tenant qa_manual | 1. Click "Transport" > "Vehicles".<br>2. Click "Add Vehicle".<br>3. Enter Vehicle Name "QA Bus 3", Registration Number "QA09XY0003", Driving Licence No. "QADL0003".<br>4. Click "Add Vehicle". | Two requests (POST then PUT); toasts "Vehicle created successfully" and "Vehicle updated successfully"; row "QA Bus 3" with Active status and Trips 0. | passing |
| TC-TRN-06-E02 | P2 | Web | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus); seeded driver Ramesh Yadav | 1. Open Transport > Vehicles and click "Add Vehicle".<br>2. Enter Vehicle Name "QA Bus 4", Registration Number "QA09XY0004", Driving Licence No. "QADL0004".<br>3. In "Trip 1" choose Route "Route 1 - Kukatpally" and Driver "Ramesh Yadav".<br>4. Click "Add Vehicle".<br>5. Open Transport > Trips. | Expected: the vehicle row shows 1 trip and Trips lists QA Bus 4 on Route 1 - Kukatpally with trip number 1. Today the vehicle saves but the trip fails because the dialog sends the staff id as driver_id. | blocked: web vehicle dialog sends the staff id as driver_id (module rule 9, Known gaps 14) |
| TC-TRN-06-E03 | P2 | Web | Admin | Seeded tenant qa_manual | 1. Open Transport > Vehicles and click "Add Vehicle".<br>2. Click "Add Vehicle" with all fields empty.<br>3. Enter Vehicle Name "QA Bus 5" and Registration Number "QA09XY0005" and click "Add Vehicle" again. | Step 2: toast "Vehicle Name and Registration Number are required"; step 3: toast "Driving Licence No. is required"; nothing is saved. | planned |
| TC-TRN-06-E04 | P2 | Web | Admin | Seeded vehicle "School Bus 1" (TS09UA1234, driver Ramesh Yadav) on Route 1 - Kukatpally | 1. Open Transport > Vehicles and click "Add Vehicle".<br>2. Enter Vehicle Name "QA Dup Bus", Registration Number "TS09UA1234", Driving Licence No. "QADL0009".<br>3. Click "Add Vehicle". | Error toast with the API message "Vehicle 'TS09UA1234' already registered"; the dialog stays usable; no second row. | planned |
| TC-TRN-06-E05 | P2 | Web | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done) | 1. Open Transport > Vehicles.<br>2. Click the Edit icon in the "QA Bus 3" row.<br>3. Enter Co-Driver Name "QA Helper" and save. | Toast "Vehicle updated successfully"; the Co-Driver column shows QA Helper. | planned |
| TC-TRN-06-E06 | P2 | Mobile | Admin | Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus); Seeded route "Route 2 - Uppal" (4 stops) | 1. Sign in as Admin on mobile.<br>2. Dashboard > "Transport" > "Vehicles".<br>3. Tap "Add Vehicle": Vehicle Name "QA Bus 6", Registration Number "QA09XY0006", Driving Licence No. "QADL0006".<br>4. In Trip 1 choose Route 1 - Kukatpally and Driver Ramesh Yadav; in Trip 2 choose Route 2 - Uppal and Driver Mohan Singh.<br>5. Tap "Add Vehicle". | Toast "Vehicle created successfully"; in "Vehicle Trips" choosing QA Bus 6 lists two trips. | planned |
| TC-TRN-06-E07 | P2 | Mobile | Admin | Vehicle "QA Bus 6" exists (TC-TRN-06-E06 done) | 1. Open the mobile Vehicles screen.<br>2. Delete "QA Bus 6" and confirm. | Toast "Vehicle deleted successfully"; the card disappears (its trips remain). | planned |
| TC-TRN-06-E08 | P2 | Mobile | Teacher | Seeded vehicle "School Bus 1" (TS09UA1234, driver Ramesh Yadav) on Route 1 - Kukatpally; Seeded vehicle "School Bus 2" (TS09UB5678, driver Mohan Singh) on Route 2 - Uppal | 1. Sign in as Teacher on mobile.<br>2. Dashboard > "Transport" > "Vehicles". | Expected: School Bus 1 and School Bus 2 are listed without "Add Vehicle". Seen 2026-10-07 on qa_school: "No Vehicles Found" although the API returns the vehicles for Teacher. | blocked: mobile Vehicles list is empty for Teacher (Known gaps 21) |
| TC-TRN-06-E09 | P3 | Web | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done) | 1. Open Transport > Vehicles.<br>2. Click the trash (Delete) icon in the "QA Bus 3" row.<br>3. In "Delete Row?" click "Delete". | Toast "Vehicle deleted successfully"; the row leaves the table. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F07 Trips

**Purpose**: Put a vehicle on a route with a driver and a trip number; students are assigned to trips.

**Roles and permissions**: `transport_trips:create`, `:list`, `:read`, `:update`, `:delete`. Admin all; Staff create, read, update, list; Teacher read and list.

**Preconditions**: A vehicle (F06), a route (F04) and optionally a driver (a user account).

**Steps, web**
1. Open `/transport/trips` (Transport > Trips; title "Trips"). Columns S.No., Vehicle, Route, Driver, Trip Number, Actions; "Export", search, inline edit and delete; pagination; empty table "No data". Teacher sees no "Add Trip"; Staff does. A separate "Trip Management" component with the same fields exists but is not routed.
2. "Add Trip" opens "Add New Trip" with native selects "Vehicle" ("Select Vehicle", options "name - registration"), "Route" ("Select Route"), "Driver" ("Select Driver", staff drivers) and "Trip Number" (default 1), buttons "Cancel" and "Add Trip". Nothing is checked before sending: with no driver the dialog sends `driver_id: ""`, the API answers 422 and the toast reads "[object Object]" (seen 2026-10-07). Toasts "Trip created!", "Trip updated!", "Trip deleted!"; other errors show the API message.

**Steps, mobile**
1. `/transport` stack hub, "Trips" (title "Trips"), search "Search trips...", "Add Trip" opens "Add Trip": "Vehicle *" ("Select vehicle"), "Route *" ("Select route"), "Driver *" ("Select driver"), "Trip Number *" (placeholder "1"), buttons "Cancel" and "Create". Validation toasts "Vehicle is required", "Route is required". Success "Trip created successfully", "Trip updated successfully", "Trip deleted successfully".

**Expected results**: A `trips` row, unique per (vehicle, route). Delete removes the row for good.

**API endpoints**
- `POST /masters/trips/` body `{vehicle_id, route_id, driver_id, trip_number}` returns 201.
- `GET /masters/trips/` (all trips, unpaginated); `GET /masters/trips/{id}`.
- `PUT /masters/trips/{id}` (full body), `PATCH /masters/trips/{id}`, `DELETE /masters/trips/{id}` (hard delete, returns the deleted trip).

**Rules and validations**
- `vehicle_id`, `route_id` and `trip_number` required; `driver_id` optional but must reference a user (`users.id`) if given.
- One trip per (vehicle, route): 400 "This vehicle is already assigned to this route". Morning and evening runs of one vehicle need different routes. The check runs on create, PUT and PATCH (when the vehicle or route changes).
- Vehicle and route ids are not checked for existence in the service; an unknown id fails in the database.
- A trip with student assignments cannot be deleted (foreign key on `student_transport_assignments.trip_id`).

**Error and edge cases**: Unknown id 404 "Trip not found". `DELETE` of a trip with assignments returns a database error response.

**Unit-testable logic**: (vehicle, route) duplicate guard on create; `exclude_unset` partial update; hard delete return value; web label formatting.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-07-U01 | `add_trip` with an existing (vehicle, route) | HTTPException 400 "This vehicle is already assigned to this route" | passing |
| TC-TRN-07-U02 | `update_partial_details_trip` changing only `trip_number` | Vehicle and route unchanged | passing |
| TC-TRN-07-U03 | `TripCreate` without `trip_number` | ValidationError | passing |
| TC-TRN-07-A01 | Admin `POST /masters/trips/` vehicle V, route R, trip_number 1, driver omitted | 201; `driver_id` null; created_at and updated_at set | passing |
| TC-TRN-07-A02 | Same (V, R) again with trip_number 2 | 400 "This vehicle is already assigned to this route" | passing |
| TC-TRN-07-A03 | Vehicle V on a second route R2 with trip_number 2 | 201 | passing |
| TC-TRN-07-A04 | Create with `driver_id` of an existing user | 201 with the id echoed | passing |
| TC-TRN-07-A05 | Create with an unknown `vehicle_id`; unknown `driver_id` | Non-2xx database error response | passing |
| TC-TRN-07-A06 | Create without `vehicle_id`; `trip_number:"a"` | 422 | passing |
| TC-TRN-07-A07 | `GET /masters/trips/` with 3 trips | Array of 3 (unpaginated, includes trips of inactive vehicles) | passing |
| TC-TRN-07-A08 | `GET /masters/trips/{id}` existing, unknown, malformed | 200; 404 "Trip not found"; 422 | passing |
| TC-TRN-07-A09 | `PUT` full body changing trip_number | 200 | passing |
| TC-TRN-07-A10 | `PATCH` changing `route_id` to a route the vehicle already serves | 400 "This vehicle is already assigned to this route" | passing |
| TC-TRN-07-A11 | `DELETE` a trip with no assignments | 200 returns the trip; `GET` then 404 | passing |
| TC-TRN-07-A12 | `DELETE` a trip that has a student assignment | Non-2xx database error; trip still exists | passing |
| TC-TRN-07-A13 | Role matrix | Admin 2xx; Staff 201 on POST, 200 on GETs, PUT and PATCH, 403 on DELETE; Teacher 200 on GETs and 403 on POST, PUT, PATCH, DELETE; Student, Parent 403 | passing |
| TC-TRN-07-A14 | Tenant isolation | Tenant B list and by-id exclude tenant A's trips | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-07-E01 | P1 | Web | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done); Seeded route "Route 2 - Uppal" (4 stops); seeded driver Mohan Singh | 1. Click "Transport" > "Trips".<br>2. Click "Add Trip".<br>3. Choose Vehicle "QA Bus 3 - QA09XY0003", Route "Route 2 - Uppal", Driver "Mohan Singh", Trip Number 1.<br>4. Click "Add Trip". | Toast "Trip created!"; the row shows QA Bus 3, Route 2 - Uppal, Mohan Singh, 1. | passing |
| TC-TRN-07-E02 | P2 | Web | Admin | Seeded vehicle "School Bus 1" (TS09UA1234, driver Ramesh Yadav) on Route 1 - Kukatpally | 1. Open Transport > Trips and click "Add Trip".<br>2. Choose Vehicle "School Bus 1 - TS09UA1234", Route "Route 1 - Kukatpally", Driver "Ramesh Yadav", Trip Number 2.<br>3. Click "Add Trip". | Error toast "This vehicle is already assigned to this route"; no second row. | planned |
| TC-TRN-07-E03 | P2 | Web | Admin | Trip from TC-TRN-07-E01 exists | 1. Open Transport > Trips.<br>2. Click the Edit icon on the QA Bus 3 row.<br>3. Change Trip Number to 2 and save. | Toast "Trip updated!"; the row shows 2. | planned |
| TC-TRN-07-E04 | P2 | Web | Admin | Trip from TC-TRN-07-E01 exists with no student assignment | 1. Open Transport > Trips.<br>2. Click the Delete icon on the QA Bus 3 row and confirm "Delete". | Toast "Trip deleted!"; the row is removed (hard delete). | planned |
| TC-TRN-07-E05 | P2 | Web | Staff | Seeded vehicle "School Bus 1" (TS09UA1234, driver Ramesh Yadav) on Route 1 - Kukatpally | 1. Sign in as Staff.<br>2. Open Transport > Trips. | The seeded trips are listed; "Add Trip" and Edit are available; the Delete control is hidden or the delete fails with a 403 error toast (Staff has no delete grant). | planned |
| TC-TRN-07-E06 | P3 | Mobile | Admin | Seeded tenant qa_manual | 1. Sign in as Admin on mobile.<br>2. Open /transport (the seven-section Transport hub).<br>3. Tap "Trips", then "Add Trip".<br>4. Leave Vehicle empty and tap "Create". | Toast "Error" with "Vehicle is required". | planned |
| TC-TRN-07-E07 | P2 | Mobile | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done); Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Open Trips on mobile and tap "Add Trip".<br>2. Choose Vehicle QA Bus 3, Route Route 1 - Kukatpally, Driver Ramesh Yadav, Trip Number 3.<br>3. Tap "Create". | Toast "Trip created successfully"; the trip card appears. | planned |
| TC-TRN-07-E08 | P3 | Web | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done); Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Open Transport > Trips and click "Add Trip".<br>2. Choose Vehicle QA Bus 3 and Route Route 1 - Kukatpally; leave Driver as "Select Driver".<br>3. Click "Add Trip". | Expected: the trip is created without a driver (driver is optional in the API). Today the dialog sends driver_id "" and the toast reads "[object Object]" (422). | blocked: web Add Trip sends an empty driver_id (Known gaps 20) |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_masters.py.

---

## F08 Transport pricing

**Purpose**: Define billing-cycle price plans (annual, semester, monthly, custom) for a vehicle, optionally for one route of that vehicle; assignments can reference a plan.

**Roles and permissions**: `transport_pricing:create`, `:list` (`GET /`, `/dropdown`), `:read` (by id), `:update` (PUT, PATCH), `:delete`. Admin all; Staff, Teacher and others none in the default catalog.

**Preconditions**: A vehicle (F06); optionally a route (F04).

**Steps, web**
1. Open `/transport/pricing` (title "Transport Pricing"; guard `transport_pricing`; Staff and Teacher get "Access Denied" with "You don't have permission to view transport pricing."). Columns S.No., Vehicle, Route, Billing Cycle, Cycle Name, Amount, Start Date, End Date, Active, Actions; "Export"; inline edit; delete with "Delete Row?" and toast "Pricing deleted successfully!".
2. "Add Pricing" opens the dialog: "Vehicle" ("Select Vehicle"), "Route" ("Select Route (optional)"), "Billing Cycle" (Annual, Semester, Monthly, Custom), "Cycle Name", "Amount (Rs)", "Start Date", "End Date", "Active". Billing Cycle defaults to Annual; submit button "Add Pricing". Vehicle, Billing Cycle, Cycle Name, Amount, Start Date and End Date are required by the API but not checked in the dialog: a missing vehicle gives "Failed to create pricing: [object Object]" (422) and the dialog closes. Success toast "Pricing "<cycle name>" created successfully!"; an overlap gives "Failed to create pricing: Overlapping pricing exists for this vehicle/route/billing_cycle (id=<id>)".

**Steps, mobile**
1. `/transport` stack hub, "Pricing" (title "Transport Pricing"; Staff sees "You don't have permission to view transport pricing"), "Add Pricing": "Vehicle *", "Route" ("Select Route (optional)"), "Billing Cycle *" (default Annual), "Cycle Name *" (placeholder "e.g. Annual 2025-26"), "Amount (Rs) *" (placeholder "e.g. 15000"), "Start Date *" (defaults to today), "End Date *" ("Select end date"), "Active", "Cancel", "Save". Validation titles "Validation": "Vehicle is required", "Billing cycle is required", "Cycle name is required", "Amount must be a positive number", "Start date is required", "End date is required", "End date must be after start date". Toasts "Created"/"Updated"/"Deleted" ("Pricing created successfully"); delete confirm "Delete Pricing".

**Expected results**: A `transport_pricing` row. Delete deactivates; the plan disappears from the list and dropdown but can still be read by id.

**API endpoints**
- `POST /masters/transport-pricing/` body `{vehicle_id, route_id, billing_cycle, cycle_name, amount, start_date, end_date, is_active}` returns 201 with `vehicle_name` and `route_name`.
- `GET /masters/transport-pricing/?vehicle_id=&billing_cycle=` (active only, newest `start_date` first); `GET /masters/transport-pricing/dropdown?vehicle_id=` (required) returns `[{id, cycle_name, billing_cycle, amount}]` ordered by `cycle_name`; `GET /masters/transport-pricing/{id}`.
- `PUT /masters/transport-pricing/{id}` (full body), `PATCH /masters/transport-pricing/{id}`, `DELETE /masters/transport-pricing/{id}`.

**Rules and validations**
- `billing_cycle` one of `annual`, `semester`, `monthly`, `custom`. `amount` greater than 0, at most 10 digits with 2 decimals (99999999.99 max). `cycle_name` max 100 in the database.
- Dates: create and PUT reject `end_date <= start_date` with 422 (validator); PATCH rejects it with 400 "end_date must be after start_date" (evaluated on the merged values).
- Vehicle must exist (404 "Vehicle not found"); route, when given, must exist (404 "Route not found").
- Overlap: among active plans with the same vehicle, the same billing cycle and the same route (a null route is compared only with other null-route plans), two ranges overlap when `existing.start < new.end` and `existing.end > new.start`. Touching boundaries (one plan ends the day the next starts) are allowed. A clash returns 400 "Overlapping pricing exists for this vehicle/route/billing_cycle (id=<uuid>)" (the module doc says 409). The check ignores inactive plans and the plan being updated.
- If more than one plan overlaps, the single-row lookup raises and the response is a 500.

**Error and edge cases**: Unknown id 404 "Transport pricing not found"; dropdown without `vehicle_id` 422; the dropdown includes expired plans and plans of other routes.

**Unit-testable logic**: `_check_overlap` predicate; date validators; PATCH merge-then-validate; dropdown ordering; amount bounds.

**Test cases**

Reference plan P1: vehicle V, route R, annual, 2026-04-01 to 2027-03-31, amount 12000.00, active.

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-08-U01 | New annual V/R plan 2027-03-31 to 2028-03-30 vs P1 | No overlap (existing.end > new.start is false) | passing |
| TC-TRN-08-U02 | New annual V/R plan 2027-03-30 to 2028-03-30 vs P1 | Overlap (existing.end 2027-03-31 > new.start 2027-03-30) | passing |
| TC-TRN-08-U03 | New annual V/R plan 2026-01-01 to 2026-04-01 vs P1 | No overlap (existing.start < new.end is false) | passing |
| TC-TRN-08-U04 | New annual V/R plan fully inside P1's range | Overlap | passing |
| TC-TRN-08-U05 | New monthly V/R plan with P1's dates | No overlap (different cycle) | passing |
| TC-TRN-08-U06 | New annual V plan with `route_id=None` and P1's dates | No overlap (null route only compares with null) | passing |
| TC-TRN-08-U07 | P1 inactive, new overlapping annual V/R plan | No overlap | passing |
| TC-TRN-08-U08 | Update P1 itself with the same dates | No overlap (excluded by id) | passing |
| TC-TRN-08-U09 | `TransportPricingCreate` with `end_date == start_date` | ValidationError "end_date must be after start_date" | passing |
| TC-TRN-08-U10 | Amount 0, 0.00, -1, 99999999.99, 100000000.00, 10.005 | Rejected, rejected, rejected, accepted, rejected, rejected | passing |
| TC-TRN-08-U11 | PATCH with only `end_date` earlier than the stored `start_date` | HTTPException 400 "end_date must be after start_date" | passing |
| TC-TRN-08-A01 | Admin `POST /masters/transport-pricing/` for V/R annual "Annual 2026-27", 12000.00, 2026-04-01 to 2027-03-31 | 201; `vehicle_name` and `route_name` populated; `amount` "12000.00" | passing |
| TC-TRN-08-A02 | Create an overlapping annual V/R plan (2026-12-01 to 2027-06-01) | 400 with message containing "Overlapping pricing exists" and P1's id | passing |
| TC-TRN-08-A03 | Create the adjacent plan 2027-03-31 to 2028-03-30 | 201 | passing |
| TC-TRN-08-A04 | Create a monthly V/R plan with P1's dates; a null-route annual plan with P1's dates | 201; 201 | passing |
| TC-TRN-08-A05 | Create with `end_date == start_date` | 422 | passing |
| TC-TRN-08-A06 | Create with `billing_cycle:"weekly"`; amount 0; missing `cycle_name` | 422 each | passing |
| TC-TRN-08-A07 | Create with an unknown `vehicle_id`; unknown `route_id` | 404 "Vehicle not found"; 404 "Route not found" | passing |
| TC-TRN-08-A08 | `GET /masters/transport-pricing/` with plans for two vehicles; `?vehicle_id=V`; `?billing_cycle=monthly` | Filters apply; active only; ordered by `start_date` descending | passing |
| TC-TRN-08-A09 | `GET /masters/transport-pricing/dropdown?vehicle_id=V` | `[{id, cycle_name, billing_cycle, amount}]` ordered by `cycle_name`, including expired plans | passing |
| TC-TRN-08-A10 | Dropdown without `vehicle_id` | 422 | passing |
| TC-TRN-08-A11 | `GET /{id}` for active, deactivated, unknown, malformed | 200, 200, 404 "Transport pricing not found", 422 | passing |
| TC-TRN-08-A12 | `PUT` full body with a new amount | 200 | passing |
| TC-TRN-08-A13 | `PATCH {"start_date":"2027-03-31"}` on a plan whose end is 2027-03-31 | 400 "end_date must be after start_date" | passing |
| TC-TRN-08-A14 | `PATCH` moving a plan into an overlapping range | 400 overlap message | passing |
| TC-TRN-08-A15 | `DELETE` P1 then create an overlapping plan | 200 `is_active=false`; the new plan returns 201 | passing |
| TC-TRN-08-A16 | Two existing overlapping active plans, then a third overlapping both | A second plan starting on the first plan's end date is 201; a third plan overlapping both is 400 | passing |
| TC-TRN-08-A17 | Role matrix | Admin 2xx; Staff, Teacher, Student, Parent 403 on every endpoint | passing |
| TC-TRN-08-A18 | Tenant isolation | Tenant B cannot read or list tenant A's plans; same dates and vehicle id from B fail with 404 vehicle | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-08-E01 | P1 | Web | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done); Seeded route "Route 2 - Uppal" (4 stops) | 1. Click "Transport" > "Pricing".<br>2. Click "Add Pricing".<br>3. Choose Vehicle "QA Bus 3", Route "Route 2 - Uppal", Billing Cycle "Annual"; enter Cycle Name "QA Annual 2026-27", Amount 13000, Start Date 2026-06-01, End Date 2027-03-31.<br>4. Click "Add Pricing". | Toast "Pricing "QA Annual 2026-27" created successfully!"; the row shows QA Bus 3, Route 2 - Uppal, Annual, Rs 13,000, the dates and Active. | passing |
| TC-TRN-08-E02 | P2 | Web | Admin | Seeded plan "Annual 2026-27" for School Bus 1 on Route 1 - Kukatpally (2026-06-01 to 2027-03-31) | 1. Open Transport > Pricing and click "Add Pricing".<br>2. Choose Vehicle School Bus 1, Route Route 1 - Kukatpally, Billing Cycle Annual; Cycle Name "QA Overlap", Amount 500, Start Date 2026-12-01, End Date 2027-06-01.<br>3. Click "Add Pricing". | Toast "Failed to create pricing: Overlapping pricing exists for this vehicle/route/billing_cycle (id=<id of the seeded plan>)"; no new row. | planned |
| TC-TRN-08-E03 | P2 | Web | Admin | Plan "QA Annual 2026-27" exists (TC-TRN-08-E01 done) | 1. Open Transport > Pricing.<br>2. Click the Edit icon on the QA Annual 2026-27 row.<br>3. Change Cycle Name to "QA Annual 26-27" and Amount to 13500, then save. | Toast "Pricing "QA Annual 26-27" updated successfully!"; the row shows the new values. | planned |
| TC-TRN-08-E04 | P2 | Web | Admin | Plan from TC-TRN-08-E03 exists | 1. Open Transport > Pricing.<br>2. Click the Delete icon on that row.<br>3. In "Delete Row?" click "Delete". | Toast "Pricing deleted successfully!"; the row disappears. | planned |
| TC-TRN-08-E05 | P2 | Web | Staff | Seeded tenant qa_manual | 1. Sign in as Staff.<br>2. Open /transport/pricing. | "Access Denied" with "You don't have permission to view transport pricing." (Teacher sees the same). | planned |
| TC-TRN-08-E06 | P3 | Mobile | Admin | Seeded vehicle "School Bus 1" (TS09UA1234, driver Ramesh Yadav) on Route 1 - Kukatpally | 1. Sign in as Admin on mobile.<br>2. Open /transport (the seven-section Transport hub).<br>3. Tap "Pricing", then "Add Pricing".<br>4. Choose Vehicle School Bus 1, Cycle Name "QA Bad Dates", Amount 100, Start Date 2027-03-01, End Date 2027-02-01.<br>5. Tap "Save". | Toast "Validation" with "End date must be after start date"; nothing is saved. | planned |
| TC-TRN-08-E07 | P2 | Mobile | Admin | Vehicle "QA Bus 3" exists (TC-TRN-06-E01 done) | 1. Open Pricing on mobile and tap "Add Pricing".<br>2. Choose Vehicle QA Bus 3, Billing Cycle Monthly, Cycle Name "QA Monthly", Amount 1200; keep Start Date (today), End Date 2027-03-31.<br>3. Tap "Save". | Toast "Created" with "Pricing created successfully"; the card appears. | planned |
| TC-TRN-08-E08 | P2 | Mobile | Admin | Plan "QA Monthly" exists (TC-TRN-08-E07 done) | 1. Open Pricing on mobile.<br>2. Delete "QA Monthly" and confirm "Delete Pricing". | Toast "Deleted" with "Pricing deleted successfully"; the card disappears. | planned |
| TC-TRN-08-E09 | P3 | Web | Admin | Seeded tenant qa_manual | 1. Open Transport > Pricing and click "Add Pricing".<br>2. Enter only Cycle Name "QA No Vehicle" and Amount 100 (no vehicle).<br>3. Click "Add Pricing". | Expected: the dialog blocks the save and names the missing fields. Today the request goes out, the API answers 422, the toast reads "Failed to create pricing: [object Object]" and the dialog closes. | blocked: web pricing dialog has no required-field check and shows 422 details as [object Object] (Known gaps 20) |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_pricing_assignment.py (overlap predicate evaluated from the real query WHERE clause).

---

## F09 Student transport assignment (staff and admin)

**Purpose**: Assign a student to a trip and a pickup stop with a fee per term and an optional pricing plan, and maintain or remove the assignment.

**Roles and permissions**: `student_transport:create`, `:list` (`GET /`), `:read` (`GET /student/{id}` for staff roles), `:update` (PATCH), `:delete`. Admin all; Staff create, read, update, list (no delete); Teacher none.

**Preconditions**: A student (admission), a trip (F07) and a stop (F05); optionally a pricing plan for the trip's vehicle (F08).

**Steps, web**
1. Open `/students/studenttransport` (Students > Student Transport; the menu entry is hidden by the sidebar filter, so use the URL or a link). For admin and staff roles the page "Student Transport" shows the assignments table (empty: "No transport assignments found."). Teacher has no `student_transport` grant and sees "Failed to load transport assignments: Permission not found in database: Teacher cannot list student_transport. Contact administrator to configure permissions."
2. Search "Search student, route, stop...". Columns S.No., Student, Trip, Route, Stop, Pricing, Fee/Term, Actions (Edit, Delete; visible with update or delete).
3. "Assign Transport" (needs `student_transport:create`) opens "Assign Transport": "Student" ("Select student..."), "Trip" ("Select trip...", listed as "Trip #<n>", so two trips with the same number look identical; the seeded trips are both "Trip #1"), "Stop" ("Select stop...", listed as "#<number> - <name>", filtered to the chosen trip's route), "Pricing Plan (optional)" (shown only when the chosen trip's vehicle has plans), and "Fee per Term (Rs)" (placeholder "e.g. 1500", min 0, step 0.01); buttons "Cancel" and "Assign". Selecting a stop prefills the fee from the stop fee ("Auto-filled from stop fee. You can edit it if needed."); selecting a student prefills it from the student's transport-type fee mapping when one exists ("Auto-loaded from the student's assigned transport fee (...)"); selecting a pricing plan prefills it from the plan amount ("Auto-filled from selected pricing plan..."). The submit button is disabled until trip, stop, fee and (on create) student are set; a fee of 0 or less is not submitted.
4. Edit opens "Edit Assignment" and sends only changed fields (trip, stop, fee, pricing). Delete opens "Delete Transport Assignment".
5. A second, raw-ID screen exists at `/transport/studentTransport` ("Student Transport" with "Add Student Transport": Trip ID, Student ID, Stop ID, Pricing ID, Fee Per Term; hidden from menus).

**Steps, mobile**
1. `/students/transport` (title "Student Transport Assignments") for non-student roles: "Assign Transport" button, "Filters", search "Search student, route, stop...", list cards with Student, Trip, Stop, "Fee / Term", pricing; "Edit" and "Delete"; empty "No transport assignments yet". The form "Assign Transport" has Student, Trip, Stop ("Select trip first"), "Pricing Plan (optional)" ("Select trip first") and "Fee per Term (Rs)" (placeholder "0.00"), buttons "Cancel" and "Assign". Validation: "Please select a trip and stop", "Please select a student", "Enter a valid fee amount"; success "Assigned", "Updated", "Removed".
2. The `/transport` stack hub "Student Transport" screen (title "Student Transport"): "Add Assignment" opens "New Assignment" (buttons "Cancel", "Create"): "Student *", "Trip *", "Stop *" ("Select a trip first"), "Fee Per Term (Rs) *" (placeholder "0"); it has no pricing picker and lists stops of every route. Messages "Student is required", "Trip is required", "Stop is required", "Enter a valid fee amount", "Transport assignment created", "Transport assignment updated", "Transport assignment deleted".

**Expected results**: A `student_transport_assignments` row (not tied to an academic year, no `is_active`, no fee term). Delete removes the row.

**API endpoints**
- `POST /students/student-transport/` body `{student_id, trip_id, stop_id, fee_per_term, pricing_id}` returns 201 with nested `student`, `trip` (with `route` and `vehicle`), `stop` and `pricing`.
- `GET /students/student-transport/` returns every assignment (unpaginated).
- `GET /students/student-transport/student/{student_id}` (F10 for self-service roles).
- `PATCH /students/student-transport/{id}` body any of `trip_id, stop_id, fee_per_term, pricing_id`.
- `DELETE /students/student-transport/{id}` returns 204.

**Rules and validations**
- Student, trip and stop must exist (404 each). Pricing, if given, must exist and be active (404 "Transport pricing not found or inactive").
- Duplicate (student, trip): 422 "Student already has transport assignment for this trip" (business-rule error; checked on create only, not when a PATCH changes the trip).
- `fee_per_term` is optional on create: when omitted it is filled from `stop.fees`; if the stop has no fee the call fails with 400 "This stop has no default fee - enter the amount manually". A fee of 0 or less is rejected: the schemas return 422, and the service returns 400 "Fee per term must be greater than 0" for values that bypass them. A stop fee of 0 is treated as "no default fee". Supplying `pricing_id` does not change the fee.
- `fee_per_term` must be greater than 0 on create, auto-fill and PATCH (the rule is `Field(gt=0)`); the response schema does not re-validate it, so an old stored 0 cannot break list calls.
- The stop must belong to the trip's route (400 "The selected stop does not belong to the route of the selected trip"), on create and when PATCH changes the trip or stop. The pricing plan is not checked against the trip's vehicle.
- `fee_per_term` is stored as a float; the pricing amount arrives as a decimal string.

**Error and edge cases**: Unknown assignment 404 "Transport assignment not found". Database errors map to an error response. Student and parent roles cannot call create, list, PATCH or DELETE (403).

**Unit-testable logic**: Fee resolution (explicit, stop default, none); negative fee guard; duplicate guard; existence checks; PATCH validation order; web prefill priority (stop, then student mapping, then pricing) and submit guard.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-09-U01 | Fee resolution with `fee_per_term=None`, `stop.fees=1200` | `resolved_fee = 1200.0` | passing |
| TC-TRN-09-U02 | `fee_per_term=None`, `stop.fees=None` | 400 "This stop has no default fee - enter the amount manually" | passing |
| TC-TRN-09-U03 | `fee_per_term=-1` and `0` | Schema 422; service 400 "Fee per term must be greater than 0" | passing |
| TC-TRN-09-U04 | `fee_per_term=1500.5` with `stop.fees=1200` | Stored 1500.5 (explicit value wins) | passing |
| TC-TRN-09-U05 | `pricing_id` given with `fee_per_term=None` and `stop.fees=900` | Fee is 900.0 (pricing amount ignored) | passing |
| TC-TRN-09-U06 | Duplicate (student, trip) | Business-rule error 422 "Student already has transport assignment for this trip" | passing |
| TC-TRN-09-U07 | `StudentTransportUpdate(fee_per_term=0)` | ValidationError (gt 0) | passing |
| TC-TRN-09-U08 | PATCH with `trip_id` to a trip the student already has | No duplicate check (no error from the service) | passing |
| TC-TRN-09-U09 | Web submit guard: fee "0", "-5", "abc", "1500.50" | Blocked, blocked, blocked, submitted as 1500.5 | blocked: submit guard is inline in the web student transport page; needs the helper exported |
| TC-TRN-09-U10 | Web fee prefill when stop fee 1200, then a student mapping fee 1500 loads | Fee field shows 1500 with the student-source hint | blocked: fee prefill is inline in web/src/pages/students/StudentTransportPage.tsx; needs the helper exported |
| TC-TRN-09-A01 | Admin `POST /students/student-transport/` student S, trip T, stop P (fees 1200), `fee_per_term` 1200 | 201 with nested student, trip.route, trip.vehicle, stop and `pricing` null; `fee_per_term` 1200.0 | passing |
| TC-TRN-09-A02 | Create without `fee_per_term` for a stop with fees 1200 | 201; `fee_per_term` 1200.0 | passing |
| TC-TRN-09-A03 | Create without `fee_per_term` for a stop with no fee | 400 "This stop has no default fee - enter the amount manually" | passing |
| TC-TRN-09-A04 | Create with `fee_per_term:-1` or `0` | 422 | passing |
| TC-TRN-09-A05 | Create the same (S, T) again | 422 "Student already has transport assignment for this trip" | passing |
| TC-TRN-09-A06 | Create for the same student on a second trip | 201 (a student may have several assignments) | passing |
| TC-TRN-09-A07 | Create with unknown student, trip, stop ids | 404 "Student not found", "Trip not found", "Route stop not found" | passing |
| TC-TRN-09-A08 | Create with a stop from a different route than the trip | 400 "The selected stop does not belong to the route of the selected trip" | passing |
| TC-TRN-09-A09 | Create with an active `pricing_id` | 201; `pricing` has `cycle_name`, `billing_cycle`, `amount`; fee is not taken from the plan | passing |
| TC-TRN-09-A10 | Create with an inactive or unknown `pricing_id` | 404 "Transport pricing not found or inactive" | passing |
| TC-TRN-09-A11 | Create with explicit `fee_per_term:0`; then `GET /students/student-transport/` | 422 (0 is rejected everywhere); a stop with fee 0 and no explicit fee gives 400 "no default fee"; no 500 | passing |
| TC-TRN-09-A12 | `GET /students/student-transport/` | Array of all assignments for the tenant with nested objects | passing |
| TC-TRN-09-A13 | `PATCH` `{fee_per_term: 1300}` | 200; fee 1300.0 | passing |
| TC-TRN-09-A14 | `PATCH {"fee_per_term":0}`; `{"fee_per_term":-5}` | 422 each | passing |
| TC-TRN-09-A15 | `PATCH` to an unknown trip or stop; unknown assignment id | 404 "Trip not found" or "Route stop not found"; 404 "Transport assignment not found" | passing |
| TC-TRN-09-A16 | `PATCH {"pricing_id": null}` | 200; pricing cleared | passing |
| TC-TRN-09-A17 | `DELETE` an assignment then `GET /student/{id}` | 204; the student has no assignments (200 with an empty list) | passing |
| TC-TRN-09-A18 | `DELETE` unknown id | 404 "Transport assignment not found" | passing |
| TC-TRN-09-A19 | Role matrix on POST, GET `/`, PATCH, DELETE | Admin 2xx; Staff 201 POST, 200 GET and PATCH, 403 DELETE; Teacher 403 all; Student, Parent 403 all | passing |
| TC-TRN-09-A20 | Tenant isolation | Assignment of tenant A absent from tenant B's list; tenant B cannot reference tenant A's student, trip or stop ids (404) | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-09-E01 | P1 | Web | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment; Seeded route "Route 1 - Kukatpally" (5 stops, Kukatpally Bus Stand to Demo School Campus) | 1. Open /students/studenttransport (page "Student Transport").<br>2. Click "Assign Transport".<br>3. Choose Student "Ananya Reddy".<br>4. Choose the "Trip #1" whose Stop list shows Route 1 stops; choose Stop "#2 - KPHB Phase 1".<br>5. Keep Fee per Term 1200 (auto-filled) and click "Assign". | Toast "Student transport created!"; the row shows Ananya Reddy, Trip #1, Route 1 - Kukatpally, KPHB Phase 1 and Fee / Term 1,200. | known defect: UI-TRN-01: choosing a trip in the Assign Transport dialog crashes the page (Something went wrong: Select.Item ... |
| TC-TRN-09-E02 | P2 | Web | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment | 1. Open /students/studenttransport and click "Assign Transport".<br>2. Choose the Route 2 trip ("Trip #1" whose stops are Uppal Ring Road and so on).<br>3. Choose Stop "#2 - Habsiguda". | Fee per Term is filled with 1300 and the hint "Auto-filled from stop fee. You can edit it if needed." appears. | planned |
| TC-TRN-09-E03 | P2 | Web | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment; seeded plans for School Bus 2 (Annual 2026-27 14000, Half Yearly 2026-27 7500) | 1. Open the Assign Transport dialog.<br>2. Choose the Route 2 trip.<br>3. Open "Pricing Plan (optional)" and choose "Half Yearly 2026-27". | "Pricing Plan (optional)" appears only after the trip is chosen; choosing the plan sets Fee per Term to 7500 with the pricing-plan hint. | planned |
| TC-TRN-09-E04 | P2 | Web | Admin | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000 | 1. Open the Assign Transport dialog.<br>2. Choose Student Karthik Reddy, the Route 1 trip and Stop "#3 - JNTU Junction", fee 1000.<br>3. Click "Assign". | Toast "Failed to create student transport"; no second row for Karthik (same student and trip). | planned |
| TC-TRN-09-E05 | P2 | Web | Admin | Assignment from TC-TRN-09-E01 exists | 1. Open /students/studenttransport.<br>2. Click Edit on the Ananya Reddy row.<br>3. In "Edit Assignment" choose Stop "#3 - JNTU Junction" and Fee 1100, then save. | Toast "Student transport updated!"; the row shows JNTU Junction and 1,100. | planned |
| TC-TRN-09-E06 | P2 | Web | Admin | Assignment from TC-TRN-09-E01 exists | 1. Open /students/studenttransport.<br>2. Click Delete on the Ananya Reddy row.<br>3. Confirm in "Delete Transport Assignment". | Toast "Student transport deleted!"; the row is removed. | planned |
| TC-TRN-09-E07 | P2 | Web | Staff | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000 | 1. Sign in as Staff.<br>2. Open /students/studenttransport. | The 8 seeded assignments are listed; "Assign Transport" and Edit are shown; Delete is hidden. | planned |
| TC-TRN-09-E08 | P1 | Mobile | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment | 1. Sign in as Admin on mobile.<br>2. Open /students/transport ("Student Transport Assignments").<br>3. Tap "Assign Transport": Student Ananya Reddy, the Route 2 trip, Stop "#3 - Tarnaka", Pricing Plan "Annual 2026-27".<br>4. Enter Fee per Term 1100 and tap "Assign". | Toast "Assigned" with "Transport assignment created successfully"; the card shows the trip, Tarnaka, the plan and Fee / Term 1100. | passing |
| TC-TRN-09-E09 | P3 | Mobile | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment | 1. Open /transport (the seven-section Transport hub).<br>2. Tap "Student Transport", then "Add Assignment" (modal "New Assignment").<br>3. Choose Student Ananya Reddy, a trip and a stop; enter Fee Per Term (Rs) * 0.<br>4. Tap "Create". | Toast "Error" with "Enter a valid fee amount"; nothing is saved. | planned |
| TC-TRN-09-E10 | P3 | Mobile | Admin | Seeded tenant qa_manual | 1. Open /students/transport and tap "Assign Transport".<br>2. Choose a trip and a stop but no student.<br>3. Tap "Assign". | Toast "Validation" with "Please select a student". | planned |
| TC-TRN-09-E11 | P2 | Mobile | Admin | Assignment from TC-TRN-09-E08 exists | 1. Open /students/transport.<br>2. Tap "Delete" on the Ananya Reddy card and confirm. | Toast "Removed" with "Transport assignment removed"; the card disappears. | planned |
| TC-TRN-09-E12 | P3 | Web | Teacher | Seeded tenant qa_manual | 1. Sign in as Teacher.<br>2. Open /students/studenttransport. | Message "Failed to load transport assignments: Permission not found in database: Teacher cannot list student_transport. Contact administrator to configure permissions."; no table. | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_pricing_assignment.py.

---

## F10 Student and parent transport view

**Purpose**: A student sees their own transport (route, stop, timings, vehicle, fee); a parent sees the transport of a linked child.

**Roles and permissions**: No permission string is checked for Student and Parent; the service verifies identity: a Student may read only their own student id, a Parent only children linked through `student_parent_links`. Other roles need `student_transport:read`. Role names are matched exactly (`Student`, `Parent`).

**Preconditions**: The student has at least one assignment (F09). For a parent, a student-parent link.

**Steps, web**
1. A Student opens `/students/studenttransport`: page "My Transport" with a card "Transport Assignment" showing Route, Timings, Vehicle, Pickup Stop, Pickup Time, Drop Time, Pricing Plan and Fee per Term. If none exists the card says "No transport assignment found."
2. A Parent sees "Children's Transport" with "Select Child" ("Child" dropdown, placeholder "Select child"); choosing a child shows a card titled "<name>'s Transport". A parent login with no linked child sees "Session outdated. Please log out and log back in."
3. The sidebar and Students hub hide the "Student Transport" menu item, so navigation is by URL.

**Steps, mobile**
1. Student and parent roles have no Transport tab or Dashboard module; the drawer entry Students > Student Transport opens `/transport/student-transport` (title "My Transport" for a student, "Child Transport" for a parent, using the child selected in the header; empty "No transport assignment found." or "Select a student from the header"). The `/students/transport` screen also supports these roles ("My Transport", "No transport assignment found").

**Expected results**: Read-only display from `GET /students/student-transport/student/{id}`.

**API endpoints**
- `GET /students/student-transport/student/{student_id}` returns the student's assignments with nested trip, route, vehicle, stop, pricing.

**Rules and validations**
- Student: 403 "You can only view your own transport assignment" when the id is not the caller's student record (matched through `students.user_id`).
- Parent: 403 "You can only view transport for your own children" when no link exists.
- Other roles: `student_transport:read` (Admin, Staff).
- A student with no assignments gets 200 with an empty list; an unknown student id gets 404 "Student not found".

**Error and edge cases**: Role spelled `student` (lowercase) falls through to the permission check and gets 403 because no `student_transport:read` grant exists.

**Unit-testable logic**: Identity guards for Student and Parent; exact role-string matching; the 404 behaviour for empty results; client handling of 404 as "no assignment".

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-10-U01 | Guard with role "Student" and a different student id | 403 "You can only view your own transport assignment" | passing |
| TC-TRN-10-U02 | Guard with role "Parent" and an unlinked child | 403 "You can only view transport for your own children" | passing |
| TC-TRN-10-U03 | Guard with role "student" (lowercase) | Falls to the permission check (403 without `student_transport:read`) | passing |
| TC-TRN-10-U04 | `get_transport_by_student_id` for a student without assignments | Empty list | passing |
| TC-TRN-10-A01 | Student calls `GET /student/{own id}` after an assignment exists | 200 with the assignment, nested route, vehicle, stop | passing |
| TC-TRN-10-A02 | Student calls it with another student's id | 403 | passing |
| TC-TRN-10-A03 | Student with no assignment calls it with their own id | 200 with an empty list | passing |
| TC-TRN-10-A04 | Parent calls it for a linked child | 200 | passing |
| TC-TRN-10-A05 | Parent calls it for an unlinked student | 403 | passing |
| TC-TRN-10-A06 | Admin and Staff call it for any student | 200 | passing |
| TC-TRN-10-A07 | Teacher calls it | 403 (no `student_transport:read`) | passing |
| TC-TRN-10-A08 | Unknown student id as Admin | 404 "Student not found" | passing |
| TC-TRN-10-A09 | No token | 401 | passing |
| TC-TRN-10-A10 | Tenant isolation: tenant B Admin requests tenant A's student id | 404 "Student not found" | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-10-E01 | P1 | Web | Student | A student created through the API for the test (QA name) that has completed first login, assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000 | 1. Sign in on web as the QA student.<br>2. Open /students/studenttransport. | Page "My Transport" with the card "Transport Assignment": Route 1 - Kukatpally, the Vehicle line with the registration number and type ("TS09UA1234 / Bus", not "School Bus 1"), Pickup Stop Kukatpally Bus Stand, Pickup Time 07:00, Drop Time 17:15, Fee per Term shown as "4,000". | passing |
| TC-TRN-10-E02 | P3 | Web | Student | Seeded student Ananya Reddy (Nursery), who has no transport assignment (student login is her admission number); first sign-in with the seeded temporary password asks for a new password | 1. Sign in on web as that student.<br>2. Open /students/studenttransport. | "My Transport" card "Transport Assignment" with "No transport assignment found."; no repeated error toasts. | planned |
| TC-TRN-10-E03 | P2 | Web | Parent | Seeded parent of Harsha Raju (004, Route 2 - Uppal, Uppal Ring Road) and Tanvi Raju (005, Route 1 - Kukatpally, KPHB Phase 1); first sign-in with the seeded temporary password asks for a new password | 1. Sign in on web as that parent.<br>2. Open /students/studenttransport.<br>3. In "Select Child" choose Harsha, then Tanvi. | "Children's Transport"; the Child dropdown lists both; "Harsha's Transport" shows Route 2 - Uppal, Uppal Ring Road; "Tanvi's Transport" shows Route 1 - Kukatpally, KPHB Phase 1. (A parent with no linked child sees "Session outdated. Please log out and log back in.") | planned |
| TC-TRN-10-E04 | P3 | Web | Student | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000; first sign-in with the seeded temporary password asks for a new password | 1. Sign in on web as student 001.<br>2. Expand Students in the sidebar.<br>3. Open /students/studenttransport by URL. | No "Student Transport" item is shown (hidden by the sidebar filter); the URL opens "My Transport". | planned |
| TC-TRN-10-E05 | P1 | Mobile | Student | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000; first sign-in with the seeded temporary password asks for a new password | 1. Sign in on mobile as student 001.<br>2. Open the drawer and choose Students > Student Transport (/transport/student-transport). | "My Transport" shows Route 1 - Kukatpally, Kukatpally Bus Stand, the timings and fee 4000. | known defect: UI-TRN-02: the mobile My Transport screen (/transport/student-transport) shows "Route: - Trip #-, Stop: -, NaN... |
| TC-TRN-10-E06 | P2 | Mobile | Parent | Seeded parent of Harsha Raju (004, Route 2 - Uppal, Uppal Ring Road) and Tanvi Raju (005, Route 1 - Kukatpally, KPHB Phase 1); first sign-in with the seeded temporary password asks for a new password | 1. Sign in on mobile as that parent.<br>2. Select Tanvi in the header student switcher.<br>3. Open the drawer and choose Students > Student Transport.<br>4. Switch to Harsha. | "Child Transport" shows Tanvi's assignment (Route 1 - Kukatpally, KPHB Phase 1), then Harsha's (Route 2 - Uppal, Uppal Ring Road). Without a selected child it says "Select a student from the header". | planned |

Implemented in (phase 1 unit tests): backend/tests/unit/transport/test_phase1_transport_pricing_assignment.py.

---

## F11 Student Trips screens and the disabled student_trips API

**Purpose**: Document the screens called "Student Trips" and the legacy `student_trips` table. The table has no API (its router is commented out in `main_router.py`); the screens are another view of `/students/student-transport/` with some dead fields and calls.

**Roles and permissions**: Backend checks are those of F09 (`student_transport:*`). Web guard on the page is `student_transport`; the create and update hooks check `transport_trips:create` and `transport_trips:update` on the client.

**Preconditions**: As F09.

**Steps, web**
1. Open `/transport/studentTrips` (hidden from the demo menu). Title "Student Transport Assignments", search "Search by name or admission number...", status filter ("All Status", "Active", "Inactive"; "Select Status").
2. "Add Assignment" opens "Add Assignment": "Trip" ("Select Trip"), "Student" ("Select Student"), "Stop" ("Select Stop"; stops of every route), "Fee Term" ("Select Fee Term"), "Fee Per Term", buttons "Cancel" and "Add Assignment". Columns S.No., Trip, Student, Stop, Fee Term, Fee Per Term, Active, Actions; "Export". Toasts "Student trip created!", "Student trip updated!", "Failed to update student trip".
3. The request sends `fee_term_id`, which the API ignores. The "Active" column reads a field that does not exist. Editing calls `PUT /students/student-transport/{id}`, which does not exist.

**Steps, mobile**
1. `/transport` stack hub "Student Trips" (title "Student Transport Assignments"): "Add New" opens "Add Transport Assignment" with "Trip *" ("Select trip"), "Student *" ("Select student"), "Stop *" ("Select a trip first"), "Fee Per Term *" (placeholder "Enter amount"), buttons "Cancel" and "Create"; search "Search by name or admission number...", status filter "Filter by status". Messages "Student transport assignment created successfully", "...updated successfully", "...deleted successfully", "Fee per term must be a positive number" and the required-field errors.

**Expected results**: Create, list and delete work against the student-transport endpoints; edit from the web fails; the status filter has no effect (no `is_active`).

**API endpoints**
- `POST/GET/PATCH/DELETE /students/student-transport/` (as F09).
- `GET /students/student-transport/{id}` and `PUT /students/student-transport/{id}` are called by the wrappers but are not routed (405 or 404).
- `/student-trips/*` (legacy router) is not mounted.

**Rules and validations**: Never send `fee_term_id`, `route_id`, `fare_amount` or `pickup_stop_id` (dead fields); never expect `is_active`.

**Error and edge cases**: Any call to a `/student-trips` path returns 404.

**Unit-testable logic**: Web wrapper URL builders; filtered list on the dead `is_active` field.

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-11-U01 | Web wrapper `updateStudentTrip(id, body)` | Targets `PUT /students/student-transport/{id}` (documents the non-routed call) | passing |
| TC-TRN-11-U02 | Status filter predicate on rows without `is_active` | "Active" filter returns no rows; "Inactive" returns all | blocked: status filter predicate is inline in the web student trips page; needs the helper exported |
| TC-TRN-11-A01 | `POST /students/student-transport/` with an extra `fee_term_id` | 201; `fee_term_id` absent from the response (silently ignored) | passing |
| TC-TRN-11-A02 | `PUT /students/student-transport/{id}` | 405 | passing |
| TC-TRN-11-A03 | `GET /students/student-transport/{id}` (single get) | 405 (only PATCH and DELETE exist on that path) | passing |
| TC-TRN-11-A04 | `GET /student-trips/` and `/api/v1/student-trips/` | 404 | passing |
| TC-TRN-11-A05 | `PATCH` and `DELETE` through the same screens' paths | As F09 | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-11-E01 | P1 | Web | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment; Seeded route "Route 2 - Uppal" (4 stops) | 1. Open /transport/studentTrips ("Student Transport Assignments").<br>2. Click "Add Assignment".<br>3. Choose a Trip (Route 2), Student Ananya Reddy, Stop Habsiguda; leave Fee Term; enter Fee Per Term 1300.<br>4. Click "Add Assignment". | Toast "Student trip created!"; the row appears and its Active column shows inactive (field missing). | passing |
| TC-TRN-11-E02 | P2 | Web | Admin | Assignment from TC-TRN-11-E01 exists | 1. Open /transport/studentTrips.<br>2. Edit the Ananya Reddy row (fee 1350) and save. | Expected: the change is saved. Today the save calls PUT /students/student-transport/{id} (405) and shows "Failed to update student trip". | blocked: web Student Trips edit uses a non-routed PUT (Known gaps 11) |
| TC-TRN-11-E03 | P3 | Web | Admin | Seeded student Karthik Reddy (001), assigned to Route 1 - Kukatpally, stop Kukatpally Bus Stand, fee 4000 | 1. Open /transport/studentTrips.<br>2. Choose "Active" in the status filter. | No rows are listed (is_active does not exist); "Inactive" lists all. | planned |
| TC-TRN-11-E04 | P2 | Mobile | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment | 1. Sign in as Admin on mobile.<br>2. Open /transport (the seven-section Transport hub).<br>3. Tap "Student Trips", then "Add New" (modal "Add Transport Assignment").<br>4. Choose Trip (Route 1), Student Ananya Reddy, Stop KPHB Phase 1; Fee Per Term * 1500.<br>5. Tap "Create". | Toast "Student transport assignment created successfully"; the card appears. Remove it afterwards (TC-TRN-09-E11 style). | planned |
| TC-TRN-11-E05 | P3 | Mobile | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment | 1. Open Student Trips on mobile and tap "Add New".<br>2. Choose trip, student and stop; enter Fee Per Term 0.<br>3. Tap "Create". | Toast "Error" with "Fee per term must be a positive number". | planned |

Implemented in (phase 1 unit tests): web/src/__tests__/transport/studentTripsApi.test.ts.

---

## F12 Transport fee effect

**Purpose**: State exactly what the transport assignment does to student fees: it stores a fee and nothing else.

**Roles and permissions**: Same as F09 and the fee module permissions for the prefill read (`fee_student_mappings` through the fee API).

**Preconditions**: A student with an assignment; optionally a fee mapping whose fee type or category name matches "transport" or "bus".

**Steps, web**
1. In "Assign Transport" (F09) select a student: if the student's fee mappings include a fee type whose name or category matches `/transport|bus/i`, the "Fee per Term (Rs)" field is prefilled with that mapping's total fee. This is a read only.
2. After saving, open the student's fees (Fee > Fee Collection or My Fees): no fee, mapping, term amount or receipt has been created or changed by the assignment.

**Steps, mobile**
1. Same assignment screens; the mobile screens do not read fee mappings, so the fee must be typed (or comes from the stop fee on the web-style prefill in `/students/transport`).

**Expected results**: `student_transport_assignments.fee_per_term` holds the amount; `GET /students/student-transport/` shows it; no row appears in `fee_student_mappings`, `fee_transactions` or any fee report because of the assignment. Fee reports show transport only if a fee type named like transport is separately mapped and collected through the fee module.

**API endpoints**: `POST /students/student-transport/` and `PATCH` (F09) for the stored value; fee mapping read `GET /fee/...` (fee module).

**Rules and validations**
- No code path in `backend/app/service/fee`, `api/v1/fee`, `models/fee` or `service/reports` refers to transport.
- `fee_per_term` is per term but there is no term, due date, billing schedule or academic year on the assignment; an assignment carries over into later years until deleted.
- Pricing plans (F08) describe amounts but are not applied automatically to assignments.

**Error and edge cases**: Deleting an assignment never touches fees. A student with transport-type fee mapping but no assignment is unaffected.

**Unit-testable logic**: Web fee-type matcher `/transport|bus/i` over `fee_category_name` plus `type_name`; first-match selection of the student's mappings (by fee type id, then by name).

**Test cases**

| ID | Scenario | Expected | Status |
|---|---|---|---|
| TC-TRN-12-U01 | Matcher over fee types "Bus Fee", "Tuition", category "Transport Charges" | "Bus Fee" and the transport category match; "Tuition" does not | blocked: fee-type matcher and first-match selection are inline in web/src/pages/students/StudentTransportPage.tsx; needs the helper exported |
| TC-TRN-12-U02 | Mapping list [Tuition 5000, Bus Fee 1500] | Selected transport fee is 1500 | blocked: fee-type matcher and first-match selection are inline in web/src/pages/students/StudentTransportPage.tsx; needs the helper exported |
| TC-TRN-12-U03 | Mapping list with no transport-like type | `transportFee` is null; field stays as the stop or manual value | blocked: fee-type matcher and first-match selection are inline in web/src/pages/students/StudentTransportPage.tsx; needs the helper exported |
| TC-TRN-12-A01 | Create an assignment with fee 1200; read `GET /fee/` student mappings and fee transactions for the student | No new mapping or transaction exists | passing |
| TC-TRN-12-A02 | Delete the assignment; repeat the fee reads | Fee data unchanged | passing |
| TC-TRN-12-A03 | Fee collection summary report before and after creating the assignment (`GET /reports/fees/collection-summary`) | Identical totals | passing |
| TC-TRN-12-A04 | `GET /students/student-transport/` after PATCH fee to 1300 | `fee_per_term` 1300.0 only here | passing |

UI test cases (manual format):

| ID | Priority | Platform | Role | Preconditions | Steps | Expected | Status |
|---|---|---|---|---|---|---|---|
| TC-TRN-12-E01 | P1 | Web | Admin | Seeded student Ananya Reddy (Nursery), who has no transport assignment; she has a fee mapping whose type or category name contains Transport or Bus (none is seeded: add one in Fee first) | 1. Open /students/studenttransport and click "Assign Transport".<br>2. Choose Student Ananya Reddy. | Fee per Term is prefilled with the mapping's total fee and the hint "Auto-loaded from the student's assigned transport fee (...)" appears. | passing |
| TC-TRN-12-E02 | P2 | Web | Admin | Assignment from TC-TRN-09-E01 exists | 1. Click "Fee" > "Fee Collection" and open Ananya Reddy.<br>2. Compare her fee lines with those before TC-TRN-09-E01. | No transport charge, mapping or term amount was added by the assignment. | planned |

---

## Known gaps

Differences between `docs/modules/transport.md` (or the UI) and the code, plus defects found while reading it. Record test outcomes against these in the Status column.

1. Pricing overlap returns 400, not 409 as the module doc says. More than one overlapping plan raises (500) because of the single-row lookup.
2. Dropdown caching: the vehicle dropdown is not cached (the module doc lists it as cached). The route dropdown cache is invalidated only on route create, not on rename, update or deactivate, so it can be stale for 5 minutes. Route type and trip type caches are invalidated on every write.
3. The module doc says the mobile hub assignment screen requires `fee_per_term` to be typed and the backend requires it; the create schema makes `fee_per_term` optional and fills it from the stop fee (400 if the stop has none). `pricing_id` never changes the fee.
4. Fixed (2026-10-02): `fee_per_term` of 0 is rejected everywhere (create, auto-fill from a stop fee of 0, PATCH, web and mobile forms); the response schema no longer inherits `gt=0`. A stop fee of 0 (web stop creation defaults a blank fee to 0) is allowed on the stop and means "no default fee".
5. Duplicate (student, trip) returns 422 (business-rule error), not 409, and is not enforced when PATCH changes the trip.
6. Fixed (2026-10-02): `GET /students/student-transport/student/{id}` returns an empty list when the student has no assignments (unknown student is still 404).
7. Trips: (vehicle, route) uniqueness is now checked on PUT and PATCH too (fixed 2026-10-02); vehicle, route and driver ids are not validated; trips are hard-deleted and cannot be deleted while assigned; `GET /masters/trips/` is unpaginated.
8. Route stops: uniqueness (route, number) includes inactive stops; route id is not validated; `fees` accepts floats in the schema but is an integer column (fractions fail); `GET /masters/route-stops/` ignores filters; the backend now rejects a stop that is not on the trip's route (fixed 2026-10-02) and the web assign dialog lists only the trip's route stops. Pricing is not checked against the trip's vehicle.
9. Route types and trip types exist only as API endpoints; there is no web or mobile screen, and the web transport options are hard-coded. Route type and trip type names (unique including inactive rows) are never validated against routes. Trip type create returns 200 and delete returns a message instead of the row.
10. Web Routes "Add Route" dialog has no inputs for the daily Up and Down Journey Time (fixed 07:00:00 and 08:30:00) and none for route type and trip type; times are editable inline in the table. Stop rows created in that dialog default fees to 0.
11. Web Student Trips page: sends the dead `fee_term_id`, edits through the non-existent `PUT /students/student-transport/{id}` (always fails), shows an "Active" column and a status filter on a field that does not exist, and gates its mutations on `transport_trips` instead of `student_transport`.
12. Web navigation: the sidebar and the Transport and Students hubs hide "Route Stops", "Transport Trips" and "Student Transport" for every role, including students and parents who need `/students/studenttransport`; those pages are reached by URL. The module doc says hubs show a "Coming Soon" banner; the transport hub code has none.
13. Mobile Transport tab shows only Routes and Vehicles; the seven-section hub at `/transport` is not linked from the tab. Mobile route-stops, trips, pricing and the student screens are reached through the routes footer, drawer menu mapping or the stack hub.
14. Web vehicle creation hard-codes `vehicle_type="Bus"`, sets inspection and pollution dates to today and sends `fee_category_id` and `fee_type_id`, which the API drops. The vehicle form requires a licence number although the API does not.
15. Deactivating a route, vehicle or pricing plan does not check or cascade to trips, stops or assignments; `GET` by id still returns inactive records.
16. No capacity field, no stop-in-route validation, no GPS or trip logs, and no fee integration (F12). The `student_trips` table is unused.
17. Mobile `/students/transport` and the web assign dialog use different fee prefill rules (mobile has no student-mapping prefill); the hub screen on mobile has no pricing picker.
18. Role comparisons in the student-transport read are exact strings (`Student`, `Parent`); a differently spelled role takes the permission path and fails with 403.
19. Web Student Transport trip options are labelled only "Trip #<n>"; trips with the same number (both seeded trips are 1) cannot be told apart until the stop list loads.
20. Web form checks seen 2026-10-07: Add Trip sends `driver_id: ""` when no driver is chosen (422, toast "[object Object]"); Add Pricing sends without a vehicle (422, toast "Failed to create pricing: [object Object]", dialog closes); Add Stop does not enforce "Up Journey Time *". The Teacher role's menu lists Students > Student Transport, which only shows a permission error.
21. Mobile Vehicles screen showed "No Vehicles Found" for Teacher on 2026-10-07 although `GET /masters/vehicles/` returns the vehicles for that role (Admin sees them).
22. UI-TRN-01: on web the Assign Transport dialog crashes when a trip is chosen ("Something went wrong!"): the pricing Select has an item with an empty-string value for the "None" option, and every seeded vehicle has pricing plans (same root cause as UI-STU-02).
23. UI-TRN-02: the mobile My Transport screen shows "Route: - Trip #-, Stop: -, NaN/term" because it treats the array response as one object.
