const fs = require('fs');
const path = require('path');
const { call } = require('./api');

const PY_HELPERS = path.join(__dirname, '..', '..', 'api_tests', 'auth', 'helpers.py');

function tempPassword(name) {
  const text = fs.readFileSync(PY_HELPERS, 'utf8');
  const match = text.match(new RegExp(`${name}\\s*=\\s*"([^"]+)"`));
  if (!match) throw new Error(`constant ${name} not found`);
  return match[1];
}

function tag() {
  return `qa.auth.${Date.now().toString(36).slice(-6)}${Math.floor(Math.random() * 900 + 100)}`;
}

function phone() {
  return `9${Array.from({ length: 9 }, () => Math.floor(Math.random() * 10)).join('')}`;
}

async function activeYear() {
  const years = await call('GET', '/auth/academic-years');
  return years.data.find((y) => y.is_active) || years.data[0];
}

async function loginAs(username, password, yearId) {
  return call('POST', '/auth/login', { body: { username, password, academic_year_id: yearId } });
}

async function activate(username, tempPass, newPass) {
  const year = await activeYear();
  const res = await loginAs(username, tempPass, year.id);
  if (res.status !== 200) throw new Error(`login failed ${res.status}`);
  if (res.data.requires_password_change) {
    const done = await call('POST', '/auth/staff/set-password', {
      body: { change_password_token: res.data.change_password_token, new_password: newPass, confirm_password: newPass },
    });
    if (done.status !== 200) throw new Error(`set-password failed ${done.status}`);
    return done.data;
  }
  return res.data;
}

async function roleIds(api) {
  const res = await api('GET', '/admin/role-mgmt/roles/');
  return Object.fromEntries(res.data.roles.map((r) => [r.name, r.id]));
}

async function createStaffUser(api, cleanup, { roleId, roleName = 'Staff' } = {}) {
  const roles = await roleIds(api);
  const id = roleId || roles[roleName];
  const t = tag();
  const email = `${t}@example.com`;
  const res = await api('POST', '/staff/enrollment', {
    body: { first_name: `Auth ${t}`, last_name: 'Tmp', email, phone: phone(), address: 'QA lane', role_id: id },
  });
  if (![200, 201].includes(res.status)) throw new Error(`enrollment failed ${res.status}`);
  const user = { username: email, userId: res.data.user_id, staffId: res.data.id, tempPassword: tempPassword('TEMP_STAFF_PASSWORD') };
  cleanup(() => api('PATCH', `/admin/users/${user.userId}`, { body: { is_active: false } }));
  cleanup(() => api('DELETE', `/staff/enrollment/${user.staffId}`));
  if (roleId && !Object.values(roles).includes(roleId)) {
    cleanup(() => api('PUT', `/admin/users/${user.userId}/role`, { body: { role_id: roles.Staff } }));
  }
  return user;
}

async function createClassAndSection(api, cleanup, year) {
  const name = `QA${tag().slice(-8)}`;
  const made = await api('POST', '/masters/class_sections/', {
    body: { name, short_code: name.slice(0, 10), academic_year_id: year.id, sections: [{ name: 'A' }] },
  });
  if (made.status !== 201) throw new Error(`class create failed ${made.status}`);
  cleanup(() => api('DELETE', `/masters/class_sections/${made.data.id}`));
  const sections = await api('GET', `/masters/class_sections/by_class_id/${made.data.id}/sections`);
  return { classId: made.data.id, className: name, sectionId: sections.data[0].id, sectionName: sections.data[0].name };
}

async function createChild(api, cleanup, year, klass, { fatherEmail, firstName }) {
  const t = tag();
  const admissionNumber = `A${t.slice(-9)}`;
  const res = await api('POST', '/students/admission/', {
    body: {
      academic_year_id: year.id,
      admitted_class_id: klass.classId,
      current_class_id: klass.classId,
      current_section_id: klass.sectionId,
      address_line1: 'QA street',
      admission_number: admissionNumber,
      student: {
        first_name: firstName,
        last_name: 'Tmp',
        date_of_birth: '2015-01-01',
        gender: 'Male',
        father: { name: `Dad ${t}`, phone: phone(), email: fatherEmail, relation_to_student: 'Father' },
        mother: { name: `Mom ${t}`, phone: phone(), relation_to_student: 'Mother' },
      },
    },
  });
  if (res.status !== 201) throw new Error(`admission failed ${res.status}`);
  cleanup(() => api('DELETE', `/students/admission/${res.data.id}`));
  return { admissionNumber, studentId: res.data.student.id, firstName, name: `${firstName} Tmp` };
}

async function createFamily(api, cleanup, names = ['Alpha', 'Bravo']) {
  const year = await activeYear();
  const klass = await createClassAndSection(api, cleanup, year);
  const t = tag();
  const fatherEmail = `${t}.dad@example.com`;
  const suffix = t.slice(-5).replace(/[0-9]/g, 'x');
  const children = [];
  for (const n of names) children.push(await createChild(api, cleanup, year, klass, { fatherEmail, firstName: `${n}${suffix}` }));
  const fatherPassword = `QA Pass ${t.slice(-6)}`;
  const data = await activate(fatherEmail, tempPassword('TEMP_PARENT_PASSWORD'), fatherPassword);
  cleanup(async () => {
    const names = [fatherEmail, ...children.flatMap((c) => [c.admissionNumber, `${c.admissionNumber}.mother`])];
    for (const name of names) {
      const users = await api('GET', `/admin/users/?search=${encodeURIComponent(name)}`);
      const rows = Array.isArray(users.data) ? users.data : users.data.users || users.data.items || [];
      const u = rows.find((r) => r.username === name);
      if (u) await api('PATCH', `/admin/users/${u.id}`, { body: { is_active: false } });
    }
  });
  return { year, klass, children, fatherEmail, fatherPassword, login: data };
}

function webAuthState(data) {
  const permissions = [];
  let id = 1;
  Object.entries(data.permissions || {}).forEach(([resource, actions]) => {
    (actions || []).forEach((action) => permissions.push({ id: String(id++), resource, action, is_granted: true }));
  });
  const students = (data.user && data.user.parent_profile && data.user.parent_profile.students) || [];
  return {
    state: {
      user: data.user,
      role: data.role,
      selectedStudent: students.length ? students[0] : null,
      availableStudents: students,
      studentId: students.length ? students[0].id : null,
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

async function injectWebSession(page, data) {
  const persisted = JSON.stringify(webAuthState(data));
  await page.addInitScript(
    ([auth, token, yearId]) => {
      if (!window.sessionStorage.getItem('__qa_injected')) {
        window.sessionStorage.setItem('__qa_injected', '1');
        window.localStorage.setItem('auth-storage', auth);
        window.localStorage.setItem('authToken', token);
      }
      if (yearId && !window.localStorage.getItem('academic-year-storage')) {
        window.localStorage.setItem('academic-year-storage', JSON.stringify({ state: { selectedAcademicYearId: yearId }, version: 0 }));
      }
    },
    [persisted, data.access_token, data.academic_year_id || null],
  );
}

async function sidebarTop(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('aside nav > ul > li > div > button[aria-label]')].map((b) => b.getAttribute('aria-label')),
  );
}

async function sidebarChildren(page, name) {
  return page.evaluate((n) => {
    const top = [...document.querySelectorAll('aside nav > ul > li')].find((li) => {
      const b = li.querySelector(':scope > div > button[aria-label]');
      return b && b.getAttribute('aria-label') === n;
    });
    if (!top) return null;
    return [...top.querySelectorAll('ul button[aria-label], ul a')].map((e) => (e.getAttribute('aria-label') || e.innerText).trim()).filter((x) => x !== n);
  }, name);
}

async function expandSidebar(page, name) {
  const btn = page.locator('aside nav').getByRole('button', { name, exact: true }).first();
  if ((await btn.getAttribute('aria-expanded')) !== 'true') await btn.click();
  await page.waitForTimeout(500);
}

async function editStorageOnNextLoad(page, entries) {
  await page.addInitScript((items) => {
    if (window.sessionStorage.getItem('__qa_edit')) return;
    window.sessionStorage.setItem('__qa_edit', '1');
    for (const [key, value] of Object.entries(items)) {
      if (value === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, value);
    }
  }, entries);
}

async function mobileFormSignInAs(page, username, password) {
  const { TENANT } = require('./api');
  await page.goto('/login', { timeout: 180_000 });
  await page.getByPlaceholder('Enter organization name').fill(TENANT);
  await page.getByText('Continue', { exact: true }).click();
  await page.getByPlaceholder('Enter your username').fill(username);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByText('Sign In', { exact: true }).click();
  await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 90_000 });
  await page.getByText('Modules', { exact: true }).locator('visible=true').first().waitFor({ timeout: 60_000 });
}

async function mobileOpenDrawer(page) {
  const width = page.viewportSize().width;
  await page.mouse.click(width - 35, 42);
}

function visibleText(page, text, options = { exact: true }) {
  return page.getByText(text, options).locator('visible=true');
}

async function grantParentRelated(api, cleanup, resource = 'student_attendance', action = 'read_related') {
  const roles = await roleIds(api);
  const roleId = roles.Parent;
  const res = await api('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=${resource}&action=${action}&is_granted=true`);
  if (res.status !== 200) throw new Error(`grant failed ${res.status}`);
  cleanup(async () => {
    const rows = await api('GET', `/auth/resource-permissions/role/${roleId}`);
    const row = rows.data.find((r) => r.resource === resource && r.action === action);
    if (row) await api('DELETE', `/auth/resource-permissions/${row.id}`);
  });
}

module.exports = {
  grantParentRelated,
  mobileFormSignInAs, mobileOpenDrawer, visibleText,
  editStorageOnNextLoad,
  tempPassword, tag, activeYear, loginAs, activate, roleIds, createStaffUser, createFamily,
  webAuthState, injectWebSession, sidebarTop, sidebarChildren, expandSidebar,
};
