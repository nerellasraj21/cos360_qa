const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const TEMPLATE = path.resolve(__dirname, '..', '..', '..', 'COS360_Full_App', 'backend', 'app', 'static', 'templates', 'staff_bulk_upload_template.xlsx');

function phone() {
  return `98${Array.from({ length: 8 }, () => Math.floor(Math.random() * 10)).join('')}`;
}

function listOf(res) {
  return Array.isArray(res.data) ? res.data : (res.data && (res.data.items || res.data.staff)) || [];
}

async function createStaff(api, cleanup, fields = {}) {
  const body = { first_name: 'QA Tmp', address: '1 QA Street', phone: phone(), ...fields };
  const res = await api('POST', '/staff/enrollment', { body });
  if (![200, 201].includes(res.status)) throw new Error(`staff enrollment failed ${res.status} ${JSON.stringify(res.data)}`);
  const staff = res.data;
  cleanup(() => api('PATCH', `/admin/users/${staff.user_id}`, { body: { is_active: false } }));
  cleanup(() => api('DELETE', `/staff/enrollment/${staff.id}`));
  return staff;
}

async function findStaffByPhone(api, phoneNo) {
  const res = await api('GET', '/staff/enrollments');
  return listOf(res).find((s) => s.phone === phoneNo);
}

async function removeStaff(api, staff) {
  if (!staff) return;
  await api('DELETE', `/staff/enrollment/${staff.id}`);
  if (staff.user_id) await api('PATCH', `/admin/users/${staff.user_id}`, { body: { is_active: false } });
}

async function designationId(api, title) {
  const res = await api('GET', '/staff/designations/dropdown');
  const found = (res.data || []).find((d) => d.title === title);
  return found && found.id;
}

function makeBulkFile(rows, name = 'qa-staff-bulk.xlsx') {
  const out = path.join(os.tmpdir(), `${Date.now().toString(36)}-${name}`);
  const script = [
    'import sys, json, openpyxl',
    'tpl, out, rows = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])',
    'wb = openpyxl.load_workbook(tpl)',
    'ws = wb["Staff Admission"]',
    'heads = {str(c.value).strip(): c.column for c in ws[1] if c.value}',
    'for i, row in enumerate(rows, start=2):',
    '    for key, val in row.items():',
    '        ws.cell(row=i, column=heads[key]).value = val',
    'wb.save(out)',
  ].join('\n');
  execFileSync('python', ['-c', script, TEMPLATE, out, JSON.stringify(rows)]);
  return out;
}

module.exports = { phone, listOf, createStaff, findStaffByPhone, removeStaff, designationId, makeBulkFile, fs };
