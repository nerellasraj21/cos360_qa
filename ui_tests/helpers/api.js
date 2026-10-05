const API_URL = (process.env.QA_API_URL || 'http://127.0.0.1:8100/api/v1').replace(/\/$/, '');
const TENANT = process.env.QA_TENANT || 'qa_school';

const ROLES = ['admin', 'staff', 'teacher', 'student', 'parent'];

function credentials(role) {
  const key = role.toUpperCase();
  const username = process.env[`QA_${key}_USER`];
  const password = process.env[`QA_${key}_PASSWORD`];
  if (!username || !password) {
    throw new Error(`QA_${key}_USER and QA_${key}_PASSWORD must be set (see e2e/.env.example)`);
  }
  return { username, password };
}

async function call(method, path, { token, body, headers } = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : { cschema: TENANT }),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  return { status: response.status, data };
}

const loginCache = new Map();

async function login(role) {
  if (loginCache.has(role)) return loginCache.get(role);
  const { username, password } = credentials(role);
  const years = await call('GET', '/auth/academic-years');
  if (years.status !== 200 || !years.data.length) {
    throw new Error(`Could not read academic years for ${TENANT}: ${years.status}`);
  }
  const active = years.data.find((y) => y.is_active) || years.data[0];
  const result = await call('POST', '/auth/login', {
    body: { username, password, academic_year_id: active.id },
  });
  if (result.status !== 200 || !result.data.access_token) {
    throw new Error(`Login failed for ${role}: ${result.status} ${JSON.stringify(result.data)}`);
  }
  loginCache.set(role, result.data);
  return result.data;
}

module.exports = { API_URL, TENANT, ROLES, credentials, call, login };
