const { unique } = require('../../helpers/fixtures');

function list(res) {
  return Array.isArray(res.data) ? res.data : (res.data && (res.data.items || res.data.data)) || [];
}

async function routeByName(api, name) {
  const res = await api('GET', '/masters/routes/all_routes?limit=1000');
  return list(res).find((r) => r.route_name === name);
}

async function stopsOf(api, routeId) {
  const res = await api('GET', '/masters/route-stops/?limit=1000');
  return list(res).filter((s) => s.route_id === routeId);
}

async function vehicleByName(api, name) {
  const res = await api('GET', '/masters/vehicles/?limit=1000');
  return list(res).find((v) => v.name === name);
}

async function driverUserId(api, fullName = 'Mohan Singh') {
  const res = await api('GET', '/staff/drivers');
  return list(res).find((d) => d.full_name === fullName).user_id;
}

async function studentByName(api, name) {
  const res = await api('GET', '/students/admission/students/dropdown/simple?active_only=true');
  return list(res).find((s) => s.name === name);
}

function code() {
  return Date.now().toString(36).slice(-5).toUpperCase() + String(Math.floor(Math.random() * 90 + 10));
}

async function createVehicle(api, cleanup, name = unique('QA Bus')) {
  const res = await api('POST', '/masters/vehicles/', {
    body: {
      name,
      registration_number: `QA${code()}`,
      vehicle_type: 'Bus',
      last_inspected_date: '2026-10-01',
      pollution_renewal_date: '2026-10-01',
      driving_licence_no: `QADL${code()}`,
      number_of_trips: 0,
    },
  });
  if (res.status !== 201) throw new Error(`vehicle create failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/masters/vehicles/${res.data.id}`));
  return res.data;
}

async function createTrip(api, cleanup, vehicleId, routeId, driverId, tripNumber = 1) {
  const res = await api('POST', '/masters/trips/', {
    body: { vehicle_id: vehicleId, route_id: routeId, driver_id: driverId, trip_number: tripNumber },
  });
  if (res.status !== 201) throw new Error(`trip create failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/masters/trips/${res.data.id}`));
  return res.data;
}

async function assignStudent(api, cleanup, { studentId, tripId, stopId, fee }) {
  const res = await api('POST', '/students/student-transport/', {
    body: { student_id: studentId, trip_id: tripId, stop_id: stopId, fee_per_term: fee },
  });
  if (res.status !== 201) throw new Error(`assignment failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/students/student-transport/${res.data.id}`));
  return res.data;
}

async function assignmentsOf(api, studentId) {
  const res = await api('GET', `/students/student-transport/student/${studentId}`);
  return list(res);
}

async function clearAssignments(api, studentId) {
  for (const a of await assignmentsOf(api, studentId)) {
    await api('DELETE', `/students/student-transport/${a.id}`);
  }
}

module.exports = {
  list,
  routeByName,
  stopsOf,
  vehicleByName,
  driverUserId,
  studentByName,
  createVehicle,
  createTrip,
  assignStudent,
  assignmentsOf,
  clearAssignments,
};
