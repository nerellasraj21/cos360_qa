const { expect } = require('../../helpers/fixtures');

async function pick(page, scope, comboName, optionName) {
  await scope.getByRole('combobox', { name: comboName, exact: true }).click();
  await page.getByRole('option', { name: optionName, exact: true }).click();
}

async function openAdmission(page) {
  await page.goto('/students/admission');
  await expect(page.getByRole('heading', { name: 'Student Admissions' })).toBeVisible({ timeout: 30_000 });
}

async function searchAdmission(page, text) {
  await page.getByRole('combobox').filter({ hasText: '100' }).first().selectOption('100');
  await page.getByPlaceholder('Search...').fill(text);
  await expect(page.locator('tbody tr').first()).toContainText(text, { timeout: 15_000 });
}

async function createAdmissionUi(page, o) {
  await page.getByRole('button', { name: 'New Admission' }).click();
  const d = page.getByRole('dialog');
  await expect(d.getByText('Step 1 of 5')).toBeVisible();
  const number = await d.getByRole('textbox', { name: 'Admission Number' }).inputValue();
  await d.getByRole('textbox', { name: 'First Name *' }).fill(o.first);
  if (o.last) await d.getByRole('textbox', { name: 'Last Name' }).fill(o.last);
  await pick(page, d, 'Select Class', o.className || 'Class 2');
  await pick(page, d, 'Select Section', o.sectionName || '2-A');
  if (o.sync !== false) await d.getByRole('checkbox', { name: 'Current Class/Section same as Admission Class/Section' }).check();
  await d.getByRole('button', { name: 'Next' }).click();
  await d.getByRole('textbox', { name: 'Name *', exact: true }).fill(o.father);
  if (o.email) await d.getByRole('textbox', { name: 'Email' }).first().fill(o.email);
  await d.getByRole('textbox', { name: 'Phone *', exact: true }).fill(o.phone);
  await d.getByRole('button', { name: 'Next' }).click();
  await d.getByRole('textbox', { name: 'Address Line 1 *' }).fill(o.address || 'QA 1 Main Road');
  await d.getByRole('button', { name: 'Next' }).click();
  await d.getByRole('button', { name: 'Next' }).click();
  await d.getByRole('button', { name: 'Create Admission' }).click();
  return number;
}

function phone() {
  return `9${Array.from({ length: 9 }, () => Math.floor(Math.random() * 10)).join('')}`;
}

async function findAdmission(api, text) {
  const res = await api('GET', '/students/admission/?limit=100');
  return (res.data.items || []).find((a) => `${a.student.first_name} ${a.student.last_name || ''}`.includes(text)) || null;
}

function trackAdmission(api, cleanup, text, extraUsers = []) {
  cleanup(async () => {
    const a = await findAdmission(api, text);
    if (!a) return;
    await api('DELETE', `/students/admission/${a.id}`);
    for (const name of [a.admission_number, `${a.admission_number}.mother`, ...extraUsers]) {
      const users = await api('GET', `/admin/users/?search=${encodeURIComponent(name)}&limit=50`);
      const u = (users.data.users || []).find((r) => r.username === name);
      if (u) await api('PATCH', `/admin/users/${u.id}`, { body: { is_active: false } });
    }
  });
}

module.exports = { pick, openAdmission, searchAdmission, createAdmissionUi, phone, findAdmission, trackAdmission };

const { activeYear, tag } = require('../../helpers/auth-users');

async function createClassAndSection(api, cleanup, year) {
  const name = `QAS${tag().slice(-8)}`;
  const made = await api('POST', '/masters/class_sections/', {
    body: { name, short_code: name.slice(0, 10), academic_year_id: year.id, sections: [{ name: 'A' }] },
  });
  if (made.status !== 201) throw new Error(`class create failed ${made.status}`);
  cleanup(() => api('DELETE', `/masters/class_sections/${made.data.id}`));
  const sections = await api('GET', `/masters/class_sections/by_class_id/${made.data.id}/sections`);
  return { classId: made.data.id, className: name, sectionId: sections.data[0].id, sectionName: sections.data[0].name };
}

async function apiClass(api, cleanup) {
  const year = await activeYear();
  const klass = await createClassAndSection(api, cleanup, year);
  return { year, ...klass };
}

async function userCleanup(api, cleanup, names) {
  cleanup(async () => {
    for (const name of names) {
      const users = await api('GET', `/admin/users/?search=${encodeURIComponent(name)}&limit=50`);
      const u = ((users.data && users.data.users) || []).find((r) => r.username === name);
      if (u) await api('PATCH', `/admin/users/${u.id}`, { body: { is_active: false } });
    }
  });
}

async function apiStudent(api, cleanup, klass, o = {}) {
  const t = tag();
  const admissionNumber = o.admissionNumber || `A${t.slice(-9)}`;
  const fatherEmail = o.fatherEmail || `${t}.dad@example.com`;
  const res = await api('POST', '/students/admission/', {
    body: {
      academic_year_id: klass.year.id,
      admitted_class_id: klass.classId,
      admitted_section_id: klass.sectionId,
      current_class_id: klass.classId,
      current_section_id: klass.sectionId,
      address_line1: 'QA street',
      admission_number: admissionNumber,
      ...(o.admissionDate ? { admission_date: o.admissionDate } : {}),
      student: {
        first_name: o.first,
        last_name: o.last || 'Tmp',
        date_of_birth: '2015-01-01',
        gender: 'Male',
        father: { name: o.father || `Dad ${t}`, phone: o.phone || phone(), email: fatherEmail, relation_to_student: 'Father' },
        mother: { name: `Mom ${t}`, phone: phone(), relation_to_student: 'Mother' },
      },
    },
  });
  if (res.status !== 201) throw new Error(`admission failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/students/admission/${res.data.id}`));
  userCleanup(api, cleanup, [admissionNumber, `${admissionNumber}.mother`, fatherEmail]);
  return { admissionId: res.data.id, studentId: res.data.student.id, admissionNumber, first: o.first, last: o.last || 'Tmp', name: `${o.first} ${o.last || 'Tmp'}`, fatherEmail };
}

Object.assign(module.exports, { apiClass, apiStudent, userCleanup });

async function seededClass(api, name = 'Class 2') {
  const res = await api('GET', '/masters/class_sections/read_all');
  const klass = res.data.find((c) => c.name === name);
  return { year: { id: klass.academic_year_id }, classId: klass.id, className: klass.name, sectionId: klass.sections[0].id, sectionName: klass.sections[0].name, sections: klass.sections };
}

Object.assign(module.exports, { seededClass });

const { call } = require('../../helpers/api');
const throwaway = require('../../helpers/throwaway');

async function makeLogin(api, cleanup, username) {
  const password = throwaway.newPassword();
  const users = await api('GET', `/admin/users/?search=${encodeURIComponent(username)}&limit=50`);
  const user = ((users.data && users.data.users) || []).find((r) => r.username === username);
  if (!user) throw new Error(`user ${username} not found`);
  const reset = await api('POST', `/admin/users/${user.id}/reset-password`, { body: { new_password: password } });
  if (reset.status !== 200) throw new Error(`reset-password failed ${reset.status}`);
  await throwaway.activate(username, password);
  return { username, password };
}

async function signInAs(page, login) {
  return throwaway.injectWeb(page, login.username, login.password);
}

Object.assign(module.exports, { makeLogin, signInAs });

const STUDENT_GRANTS = [
  ['student_admissions', 'read_own'], ['student_admissions', 'list_own'],
  ['student_attendance', 'read_own'], ['student_attendance', 'list_own'],
  ['student_certificates', 'read_own'], ['student_certificates', 'list_own'],
];
const PARENT_GRANTS = [
  ['student_admissions', 'read_related'], ['student_admissions', 'list_related'],
  ['student_attendance', 'read_related'], ['student_attendance', 'list_related'],
  ['student_certificates', 'read_related'], ['student_certificates', 'list_related'],
];

async function grantRole(api, cleanup, roleName, pairs) {
  const roles = await api('GET', '/admin/role-mgmt/roles/');
  const roleId = roles.data.roles.find((r) => r.name === roleName).id;
  for (const [resource, action] of pairs) {
    const rows = await api('GET', `/auth/resource-permissions/role/${roleId}`);
    const existing = (rows.data || []).find((r) => r.resource === resource && r.action === action);
    if (existing && existing.is_granted) continue;
    const res = await api('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=${resource}&action=${action}&is_granted=true`);
    if (res.status !== 200) throw new Error(`grant ${resource}:${action} failed ${res.status}`);
    cleanup(async () => {
      const now = await api('GET', `/auth/resource-permissions/role/${roleId}`);
      const row = (now.data || []).find((r) => r.resource === resource && r.action === action);
      if (!row) return;
      if (existing) await api('PUT', `/admin/role-mgmt/roles/${roleId}/permissions?resource=${resource}&action=${action}&is_granted=false`);
      else await api('DELETE', `/auth/resource-permissions/${row.id}`);
    });
  }
}

Object.assign(module.exports, { STUDENT_GRANTS, PARENT_GRANTS, grantRole });
