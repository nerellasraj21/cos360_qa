const { call, login, TENANT } = require('./api');

function tag() {
  return `${Date.now().toString(36).slice(-5)}${Math.floor(Math.random() * 900 + 100)}`;
}

function phone() {
  return `9${String(Math.floor(Math.random() * 1e9)).padStart(9, '0')}`;
}

function newPassword(label = 'QA Pass') {
  return `${label} ${tag()}`;
}

async function adminToken() {
  return (await login('admin')).access_token;
}

async function activeYear() {
  const years = await call('GET', '/auth/academic-years');
  return (years.data.find((y) => y.is_active) || years.data[0]).id;
}

async function roleIds(token) {
  const res = await call('GET', '/admin/role-mgmt/roles/', { token });
  return Object.fromEntries(res.data.roles.map((r) => [r.name, r.id]));
}

async function plainLogin(username, password, yearId) {
  const year = yearId || (await activeYear());
  return call('POST', '/auth/login', { body: { username, password, academic_year_id: year } });
}

async function activate(username, password) {
  const res = await plainLogin(username, password);
  if (res.status === 200 && res.data.requires_password_change) {
    const done = await call('POST', '/auth/staff/set-password', {
      body: { change_password_token: res.data.change_password_token, new_password: password, confirm_password: password },
    });
    if (done.status !== 200) throw new Error(`set-password failed: ${done.status}`);
    return done.data;
  }
  if (res.status !== 200) throw new Error(`login failed: ${res.status}`);
  return res.data;
}

async function findUser(token, search, username) {
  const res = await call('GET', `/admin/users/?search=${encodeURIComponent(search)}&limit=100`, { token });
  const user = (res.data.users || []).find((u) => u.username === username);
  if (!user) throw new Error(`user ${username} not found`);
  return user;
}

async function makeLoginUsable(token, cleanup, user, password) {
  const reset = await call('POST', `/admin/users/${user.id}/reset-password`, { token, body: { new_password: password } });
  if (reset.status !== 200) throw new Error(`reset-password failed: ${reset.status}`);
  cleanup(() => call('PATCH', `/admin/users/${user.id}`, { token, body: { is_active: false } }));
  await activate(user.username, password);
}

async function createStaffUser(cleanup, { role = 'Staff', label = 'Auth' } = {}) {
  const token = await adminToken();
  const roles = await roleIds(token);
  const id = tag();
  const email = `qa.auth.${id}@example.com`;
  const body = {
    first_name: `QA${label}${id}`,
    last_name: 'Throwaway',
    email,
    phone: phone(),
    address: 'QA lane',
    role_id: roles[role],
  };
  const res = await call('POST', '/staff/enrollment/', { token, body });
  if (![200, 201].includes(res.status)) throw new Error(`staff enrollment failed: ${res.status}`);
  const staffId = res.data.id;
  cleanup(() => call('DELETE', `/staff/enrollment/${staffId}`, { token }));
  const user = await findUser(token, email, email);
  const password = newPassword();
  await makeLoginUsable(token, cleanup, user, password);
  return { userId: user.id, staffId, username: email, email, phone: body.phone, firstName: body.first_name, lastName: body.last_name, password, role };
}

async function createFamily(cleanup) {
  const token = await adminToken();
  const year = await activeYear();
  const id = tag();
  const cls = await call('POST', '/masters/class_sections/', {
    token,
    body: { name: `QAAuth${id}`, short_code: `QA${id}`.slice(0, 10), academic_year_id: year, sections: [{ name: 'A' }] },
  });
  if (cls.status !== 201) throw new Error(`class create failed: ${cls.status}`);
  const classId = cls.data.id;
  cleanup(() => call('DELETE', `/masters/class_sections/${classId}`, { token }));
  const sections = await call('GET', `/masters/class_sections/by_class_id/${classId}/sections`, { token });
  const admissionNumber = `qa.auth.${id}`;
  const fatherEmail = `qa.auth.${id}.dad@example.com`;
  const adm = await call('POST', '/students/admission/', {
    token,
    body: {
      academic_year_id: year,
      admitted_class_id: classId,
      current_class_id: classId,
      current_section_id: sections.data[0].id,
      address_line1: 'QA street',
      admission_number: admissionNumber,
      student: {
        first_name: `QAKid${id}`,
        last_name: 'Throwaway',
        date_of_birth: '2015-01-01',
        gender: 'Male',
        father: { name: `QA Dad ${id}`, phone: phone(), email: fatherEmail, relation_to_student: 'Father' },
        mother: { name: `QA Mom ${id}`, phone: phone(), relation_to_student: 'Mother' },
      },
    },
  });
  if (adm.status !== 201) throw new Error(`admission failed: ${adm.status}`);
  const admissionId = adm.data.id;
  cleanup(() => call('DELETE', `/students/admission/${admissionId}`, { token }));
  const studentUser = await findUser(token, admissionNumber, admissionNumber);
  const fatherUser = await findUser(token, fatherEmail, fatherEmail);
  const motherUser = await findUser(token, `${admissionNumber}.mother`, `${admissionNumber}.mother`);
  const studentPassword = newPassword();
  const fatherPassword = newPassword();
  await makeLoginUsable(token, cleanup, studentUser, studentPassword);
  await makeLoginUsable(token, cleanup, fatherUser, fatherPassword);
  cleanup(() => call('PATCH', `/admin/users/${motherUser.id}`, { token, body: { is_active: false } }));
  return {
    studentId: adm.data.student.id,
    studentName: `QAKid${id} Throwaway`,
    className: `QAAuth${id}`,
    admissionNumber,
    studentPassword,
    studentUserId: studentUser.id,
    fatherEmail,
    fatherPassword,
    fatherUserId: fatherUser.id,
    fatherName: `QA Dad ${id}`,
  };
}

async function grantProfile(cleanup, roleName, actions = ['read_own', 'update_own']) {
  const token = await adminToken();
  const roles = await roleIds(token);
  const roleId = roles[roleName];
  for (const action of actions) {
    const res = await call('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=profile&action=${action}&is_granted=true`, { token });
    if (res.status !== 200) throw new Error(`grant failed: ${res.status}`);
    const old = res.data.permission && res.data.permission.old_value;
    cleanup(async () => {
      if (old === null || old === undefined) {
        const rows = await call('GET', `/auth/resource-permissions/role/${roleId}`, { token });
        const row = (rows.data || []).find((r) => r.resource === 'profile' && r.action === action);
        if (row) await call('DELETE', `/auth/resource-permissions/${row.id}`, { token });
      } else {
        await call('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=profile&action=${action}&is_granted=${old ? 'true' : 'false'}`, { token });
      }
    });
  }
}

function webAuthState(data) {
  const permissions = [];
  let n = 1;
  Object.entries(data.permissions || {}).forEach(([resource, actions]) => {
    (actions || []).forEach((action) => permissions.push({ id: String(n++), resource, action, is_granted: true }));
  });
  const students = (data.user && data.user.parent_profile && data.user.parent_profile.students) || [];
  const roleName = data.role.name.toLowerCase();
  let studentId = null;
  if (roleName === 'student') studentId = data.entity_id || data.user.id;
  else if (roleName === 'parent' && students.length) studentId = students[0].id;
  return {
    state: {
      user: data.user,
      role: data.role,
      selectedStudent: students.length ? students[0] : null,
      availableStudents: students,
      studentId,
      entityId: data.entity_id || null,
      academicYearId: data.academic_year_id || null,
      academicYearTitle: data.academic_year_title || null,
      permissions,
      permissionsMap: data.permissions || {},
      menuItems: data.menu,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      isAuthenticated: true,
    },
    version: 0,
  };
}

async function injectWeb(page, username, password) {
  const data = await activate(username, password);
  await page.addInitScript(
    ([auth, accessToken, yearId]) => {
      window.localStorage.setItem('auth-storage', auth);
      window.localStorage.setItem('authToken', accessToken);
      if (yearId && !window.localStorage.getItem('academic-year-storage')) {
        window.localStorage.setItem('academic-year-storage', JSON.stringify({ state: { selectedAcademicYearId: yearId }, version: 0 }));
      }
    },
    [JSON.stringify(webAuthState(data)), data.access_token, data.academic_year_id || null],
  );
  return data;
}

async function injectMobile(page, username, password) {
  const data = await activate(username, password);
  const permissions = [];
  Object.entries(data.permissions || {}).forEach(([resource, actions]) => {
    (actions || []).forEach((action) => permissions.push({ id: `${resource}:${action}`, resource, action, is_granted: true }));
  });
  const items = {
    '@secure/auth_access_token': data.access_token,
    '@secure/auth_refresh_token': data.refresh_token,
    '@secure/auth_token_expiry': String(Date.now() + (data.expires_in || 3600) * 1000),
    '@active_academic_year': data.academic_year_id || '',
    '@auth/client_schema': TENANT,
    '@auth/role_data': JSON.stringify(data.role),
    '@auth/menu_data': JSON.stringify(data.menu || []),
    '@auth/user_data': JSON.stringify(data.user),
    '@auth/permissions_data': JSON.stringify(permissions),
  };
  await page.addInitScript((entries) => {
    for (const [k, v] of Object.entries(entries)) window.localStorage.setItem(k, v);
  }, items);
  return data;
}

module.exports = {
  tag,
  newPassword,
  adminToken,
  activeYear,
  plainLogin,
  activate,
  findUser,
  createStaffUser,
  createFamily,
  grantProfile,
  injectWeb,
  injectMobile,
  roleIds,
};
