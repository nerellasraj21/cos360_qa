const { expect } = require('../../helpers/fixtures');
const students = require('../students/_kit');

async function apiType(api, cleanup, name) {
  const res = await api('POST', '/certificates/types/', { body: { name, description: 'QA type' } });
  if (res.status !== 201) throw new Error(`type create failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/certificates/types/${res.data.id}`));
  return res.data;
}

async function typeIdByName(api, name) {
  const res = await api('GET', '/certificates/types/?limit=100');
  const rows = (res.data && res.data.items) || [];
  return (rows.find((r) => r.name === name) || {}).id;
}

async function cleanupCertificates(api, cleanup, studentId) {
  cleanup(async () => {
    const res = await api('GET', `/certificates/by-student/${studentId}`);
    const items = (res.data && (res.data.items || res.data.certificates)) || [];
    for (const c of items) await api('DELETE', `/certificates/${c.id}`);
  });
}

async function selectStudent(page, klass, student) {
  await page.goto('/students/studentcertificates');
  await expect(page.getByRole('heading', { name: 'Student Certificates' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'Select class' }).click();
  await page.getByRole('button', { name: klass.className, exact: true }).click();
  await page.getByRole('button', { name: 'All sections' }).click();
  await page.getByRole('button', { name: klass.sectionName, exact: true }).click();
  await page.getByRole('button', { name: 'Select student' }).click();
  await page.getByRole('button', { name: `${student.name} (${student.admissionNumber})` }).click();
  await expect(page.getByText(`Upload for ${student.name}`)).toBeVisible({ timeout: 20_000 });
}

module.exports = { ...students, apiType, typeIdByName, cleanupCertificates, selectStudent };

const fs = require('fs');
const path = require('path');
const { login } = require('../../helpers/api');

const PDF = path.join(__dirname, 'files', 'qa-doc.pdf');

async function apiUpload(kind, studentId, typeId, extra = {}) {
  const token = (await login('admin')).access_token;
  const form = new FormData();
  form.append('student_id', studentId);
  form.append('certificate_type_id', typeId);
  if (extra.remarks) form.append('remarks', extra.remarks);
  if (kind === 'issued') form.append('issue_date', extra.issueDate || new Date().toISOString().slice(0, 10));
  form.append('file', new Blob([fs.readFileSync(PDF)], { type: 'application/pdf' }), 'qa-doc.pdf');
  const base = (process.env.QA_API_URL || 'http://127.0.0.1:8100/api/v1').replace(/\/$/, '');
  const res = await fetch(`${base}/certificates/${kind}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form });
  if (res.status !== 201) throw new Error(`upload ${kind} failed ${res.status} ${await res.text()}`);
  return res.json();
}

module.exports.apiUpload = apiUpload;
module.exports.PDF = PDF;
