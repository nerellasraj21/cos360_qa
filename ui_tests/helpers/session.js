const { login, credentials, TENANT } = require('./api');

function webAuthState(data) {
  const permissions = [];
  let id = 1;
  Object.entries(data.permissions || {}).forEach(([resource, actions]) => {
    (actions || []).forEach((action) => {
      permissions.push({ id: String(id++), resource, action, is_granted: true });
    });
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

async function signInWeb(page, role) {
  const data = await login(role);
  const persisted = JSON.stringify(webAuthState(data));
  await page.addInitScript(
    ([auth, token, yearId]) => {
      window.localStorage.setItem('auth-storage', auth);
      window.localStorage.setItem('authToken', token);
      if (yearId && !window.localStorage.getItem('academic-year-storage')) {
        window.localStorage.setItem('academic-year-storage', JSON.stringify({ state: { selectedAcademicYearId: yearId }, version: 0 }));
      }
    },
    [persisted, data.access_token, data.academic_year_id || null],
  );
  return data;
}

async function signInMobile(page, role) {
  const data = await login(role);
  await page.addInitScript(
    ([access, refresh, tenant]) => {
      window.localStorage.setItem('@auth/access_token', access);
      window.localStorage.setItem('@auth/refresh_token', refresh);
      window.localStorage.setItem('@auth/client_schema', tenant);
    },
    [data.access_token, data.refresh_token, TENANT],
  );
  return data;
}


async function signInMobileViaForm(page, role) {
  const { username, password } = credentials(role);
  await page.goto('/login');
  await page.getByPlaceholder('Enter organization name').fill(TENANT);
  await page.getByText('Continue', { exact: true }).click();
  await page.getByPlaceholder('Enter your username').fill(username);
  await page.getByPlaceholder('Enter your password').fill(password);
  await page.getByText('Sign In', { exact: true }).click();
  await page.waitForFunction(() => !location.pathname.includes('login'), null, { timeout: 45_000 });
  await page.waitForTimeout(3000);
}

module.exports = { signInWeb, signInMobile, signInMobileViaForm };
