const fs = require('fs');
const path = require('path');
const { call, login, credentials, TENANT } = require('./api');

const APP_ROOT = path.resolve(__dirname, '..', '..', '..', 'COS360_Full_App', 'backend', 'app', 'service');

function tempPassword(file, index = 0) {
  const src = fs.readFileSync(path.join(APP_ROOT, file), 'utf8');
  const found = [...src.matchAll(/hash_password\("([^"]+)"\)/g)].map((m) => m[1]);
  return found[index];
}

const TEMP = {
  staff: () => tempPassword('masters/staff_service.py'),
  student: () => tempPassword('student/admission_service.py', 0),
  parent: () => tempPassword('student/admission_service.py', 1),
};

function phone() {
  return '9' + String(Math.floor(Math.random() * 1e9)).padStart(9, '0');
}

function tag() {
  return `${Date.now().toString(36).slice(-5)}${Math.floor(Math.random() * 900 + 100)}`.toLowerCase();
}

async function adminCall(method, apiPath, body) {
  const admin = await login('admin');
  return call(method, apiPath, { token: admin.access_token, body });
}

async function activeYear() {
  const years = await call('GET', '/auth/academic-years');
  return years.data.find((y) => y.is_active) || years.data[0];
}

async function createStaffUser(cleanup) {
  const t = `qa.auth.${tag()}`;
  const email = `${t}@example.com`;
  const res = await adminCall('POST', '/staff/enrollment', {
    first_name: `QA Auth ${t}`,
    last_name: 'Tmp',
    email,
    phone: phone(),
    address: 'QA lane',
  });
  if (![200, 201].includes(res.status)) throw new Error(`staff enrollment failed ${res.status}`);
  const user = { username: email, password: TEMP.staff(), userId: res.data.user_id, staffId: res.data.id };
  cleanup(() => adminCall('DELETE', `/staff/enrollment/${user.staffId}`));
  cleanup(() => adminCall('PATCH', `/admin/users/${user.userId}`, { is_active: false }));
  return user;
}

async function createFamily(cleanup) {
  const t = `qa.auth.${tag()}`;
  const year = await activeYear();
  const cls = await adminCall('POST', '/masters/class_sections/', {
    name: `QA Auth ${t}`.slice(0, 40),
    short_code: t.slice(-10),
    academic_year_id: year.id,
    sections: [{ name: 'A' }],
  });
  if (cls.status !== 201) throw new Error(`class create failed ${cls.status}`);
  cleanup(() => adminCall('DELETE', `/masters/class_sections/${cls.data.id}`));
  const sections = await adminCall('GET', `/masters/class_sections/by_class_id/${cls.data.id}/sections`);
  const admissionNumber = `QA${tag()}`.toUpperCase();
  const fatherEmail = `${t}.dad@example.com`;
  const res = await adminCall('POST', '/students/admission/', {
    academic_year_id: year.id,
    admitted_class_id: cls.data.id,
    current_class_id: cls.data.id,
    current_section_id: sections.data[0].id,
    address_line1: 'QA street',
    admission_number: admissionNumber,
    student: {
      first_name: `QA Kid ${t}`,
      last_name: 'Tmp',
      date_of_birth: '2015-01-01',
      gender: 'Male',
      father: { name: `QA Dad ${t}`, phone: phone(), email: fatherEmail, relation_to_student: 'Father' },
      mother: { name: `QA Mom ${t}`, phone: phone(), relation_to_student: 'Mother' },
    },
  });
  if (res.status !== 201) throw new Error(`admission failed ${res.status}`);
  const users = await adminCall('GET', `/admin/users/?search=${encodeURIComponent(t)}&limit=50`);
  const rows = Array.isArray(users.data) ? users.data : users.data.items || users.data.users || [];
  const family = {
    admissionNumber,
    fatherEmail,
    studentPassword: TEMP.student(),
    parentPassword: TEMP.parent(),
    userIds: rows.map((u) => u.id),
  };
  cleanup(() => adminCall('DELETE', `/students/admission/${res.data.id}`));
  cleanup(async () => {
    for (const id of family.userIds) await adminCall('PATCH', `/admin/users/${id}`, { is_active: false });
    const again = await adminCall('GET', `/admin/users/?search=${encodeURIComponent(admissionNumber)}&limit=50`);
    const more = Array.isArray(again.data) ? again.data : again.data.items || again.data.users || [];
    for (const u of more) await adminCall('PATCH', `/admin/users/${u.id}`, { is_active: false });
  });
  return family;
}

async function webSubmitLogin(page, username, password, yearTitle) {
  await page.goto('/login');
  await page.getByRole('button', { name: /^\d{4}-\d{4}/ }).first().waitFor({ timeout: 20_000 });
  if (yearTitle) {
    await page.getByRole('button', { name: /^\d{4}-\d{4}/ }).first().click();
    await page.getByRole('button', { name: yearTitle, exact: true }).click();
  }
  await page.getByLabel('Username / Admission Number').fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Login' }).click();
}

async function mobileOpenForm(page, org = TENANT) {
  await page.goto('/login', { timeout: 180_000 });
  await page.getByPlaceholder('Enter organization name').fill(org);
  await page.getByText('Continue', { exact: true }).click();
  await page.getByPlaceholder('Enter your username').waitFor({ timeout: 60_000 });
}

async function mobileSubmitLogin(page, username, password) {
  await page.getByPlaceholder('Enter your username').fill(username);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByText('Sign In', { exact: true }).click();
}

async function restoreYear(title = '2026-2027') {
  const years = await adminCall('GET', '/masters/academic_years/?active_only=false&limit=1000');
  const rows = Array.isArray(years.data) ? years.data : years.data.items || [];
  const base = rows.find((y) => y.title === title);
  if (base && !base.is_active) await adminCall('PUT', `/masters/academic_years/${base.id}`, { is_active: true });
}

async function createInactiveYear(cleanup, title, start = '2031-04-01', end = '2032-03-31') {
  const res = await adminCall('POST', '/masters/academic_years/', { title, start_date: start, end_date: end, is_active: false });
  if (![200, 201].includes(res.status)) throw new Error(`year create failed ${res.status}`);
  cleanup(() => adminCall('DELETE', `/masters/academic_years/${res.data.id}/permanent`));
  cleanup(() => restoreYear());
  return res.data;
}

module.exports = {
  TEMP, TENANT, credentials, adminCall, activeYear, createStaffUser, createFamily,
  webSubmitLogin, mobileOpenForm, mobileSubmitLogin, restoreYear, createInactiveYear, call,
};

async function mobileReachSetPassword(page) {
  const heading = page.getByText('Set New Password').first();
  await heading.waitFor({ timeout: 15_000 });
  await page.waitForTimeout(1500);
  await require('@playwright/test').expect(heading).toBeVisible({ timeout: 2000 });
}
module.exports.mobileReachSetPassword = mobileReachSetPassword;

async function activateViaApi(username, tempPassword) {
  const year = await activeYear();
  const first = await call('POST', '/auth/login', { body: { username, password: tempPassword, academic_year_id: year.id } });
  if (!first.data || !first.data.change_password_token) throw new Error(`no first-login challenge ${first.status}`);
  const next = `QA Pass ${tag()}`;
  const done = await call('POST', '/auth/staff/set-password', {
    body: { change_password_token: first.data.change_password_token, new_password: next, confirm_password: next },
  });
  if (done.status !== 200) throw new Error(`set-password failed ${done.status}`);
  return next;
}
module.exports.activateViaApi = activateViaApi;
module.exports.tag = tag;

async function webLogout(page) {
  await page.getByRole('button', { name: /^\w ?\S+$/ }).filter({ hasText: /qa\.|qa_/ }).first().click();
  await page.getByText('Logout', { exact: true }).click();
}
module.exports.webLogout = webLogout;
