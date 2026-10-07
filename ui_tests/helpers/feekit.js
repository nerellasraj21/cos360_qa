const { call, login } = require('./api');

function tag() {
  return `${Date.now().toString(36).slice(-5)}${Math.floor(Math.random() * 900 + 100)}`;
}

function phone() {
  return `9${String(Math.floor(Math.random() * 1e9)).padStart(9, '0')}`;
}

async function admin(method, path, body) {
  const a = await login('admin');
  return call(method, path, { token: a.access_token, body });
}

async function yearId() {
  const years = await call('GET', '/auth/academic-years');
  return (years.data.find((y) => y.is_active) || years.data[0]).id;
}

function must(res, label, ok = [200, 201]) {
  if (!ok.includes(res.status)) throw new Error(`${label} failed ${res.status} ${JSON.stringify(res.data).slice(0, 300)}`);
  return res.data;
}

async function createCategory(cleanup, name) {
  const data = must(await admin('POST', '/fee/categories/', { category_name: name, category_status: 'active', academic_year_id: await yearId() }), 'category');
  cleanup(() => admin('DELETE', `/fee/categories/${data.id}`));
  return data;
}

async function createTerm(cleanup, name, dates = ['2026-06-10', '2026-09-10', '2026-12-10', '2027-03-10']) {
  const data = must(await admin('POST', '/fee/terms/', {
    term_name: name, term_status: 'active', number_of_terms: dates.length, academic_year_id: await yearId(),
    fee_term_dates: dates.map((d) => ({ fee_term_date: d })),
  }), 'term');
  cleanup(() => admin('DELETE', `/fee/terms/${data.id}`));
  return data;
}

async function createType(cleanup, name, categoryId, termId) {
  const data = must(await admin('POST', '/fee/types/', {
    type_name: name, fee_category_id: categoryId, fee_status: 'active', fee_term_id: termId, academic_year_id: await yearId(),
  }), 'type');
  cleanup(() => admin('DELETE', `/fee/types/${data.id}`));
  return data;
}

async function createClassMapping(cleanup, classId, typeId, total, mandatory = false) {
  const data = must(await admin('POST', '/fee/class-mappings/', {
    class_id: classId, fee_type_id: typeId, total_fee: total, academic_year_id: await yearId(), all_by_default: mandatory,
  }), 'class mapping');
  cleanup(() => admin('DELETE', `/fee/class-mappings/${data.id}`));
  return data;
}

async function createStudentMapping(cleanup, student, typeId, total) {
  const data = must(await admin('POST', '/fee/student-mappings/', {
    student_id: student.studentId, student_admission_num: student.admissionNumber, class_id: student.classId,
    section_id: student.sectionId, fee_type_id: typeId, total_fee: total, academic_year_id: await yearId(),
  }), 'student mapping');
  cleanup(() => admin('DELETE', `/fee/student-mappings/${data.id}`));
  return data;
}

async function createStudent(cleanup, opts = {}) {
  const t = tag();
  const year = await yearId();
  const cls = must(await admin('POST', '/masters/class_sections/', {
    name: `QA Fee ${t}`.slice(0, 40), short_code: t.slice(-8), academic_year_id: year, sections: [{ name: 'A' }],
  }), 'class');
  cleanup(() => admin('DELETE', `/masters/class_sections/${cls.id}`));
  const sections = must(await admin('GET', `/masters/class_sections/by_class_id/${cls.id}/sections`), 'sections');
  const admissionNumber = `QF${t}`.toUpperCase();
  const father = opts.father || { name: `QA Dad ${t}`, phone: phone(), email: `qa.fee.${t}.dad@example.com`, relation_to_student: 'Father' };
  const first = `QAFee${t}`;
  const res = must(await admin('POST', '/students/admission/', {
    academic_year_id: year, admitted_class_id: cls.id, current_class_id: cls.id, current_section_id: sections[0].id,
    address_line1: 'QA street', admission_number: admissionNumber,
    student: {
      first_name: first, last_name: 'Kid', date_of_birth: '2015-01-01', gender: 'Male', father,
      mother: { name: `QA Mom ${t}`, phone: phone(), relation_to_student: 'Mother' },
    },
  }), 'admission');
  const student = {
    studentId: res.student.id, admissionId: res.id, admissionNumber, name: `${first} Kid`, firstName: first,
    classId: cls.id, className: cls.name, sectionId: sections[0].id, sectionName: sections[0].name, tag: t, father,
  };
  cleanup(async () => {
    await admin('DELETE', `/students/admission/${res.id}`);
    const users = await admin('GET', `/admin/users/?search=${encodeURIComponent(t)}&limit=50`);
    const rows = (users.data && (users.data.users || users.data.items)) || [];
    for (const u of rows) await admin('PATCH', `/admin/users/${u.id}`, { is_active: false });
    const again = await admin('GET', `/admin/users/?search=${encodeURIComponent(admissionNumber)}&limit=50`);
    for (const u of ((again.data && (again.data.users || again.data.items)) || [])) await admin('PATCH', `/admin/users/${u.id}`, { is_active: false });
  });
  return student;
}

async function pay(student, items, method = 'cash', extra = {}) {
  const total = items.reduce((s, i) => s + i.amount, 0);
  return admin('POST', '/fee/collection/pay', {
    student_id: student.studentId, academic_year_id: await yearId(), amount_to_pay: total,
    fee_items: items.map((i) => ({ fee_type_id: i.typeId, amount: i.amount })), payment_method: method, send_sms: false, ...extra,
  });
}

module.exports = {
  tag, admin, yearId, must, createCategory, createTerm, createType, createClassMapping, createStudentMapping, createStudent, pay,
};

async function classIdByName(name) {
  const res = await admin('GET', '/masters/class_sections/dropdown');
  const row = (res.data || []).find((c) => c.name === name || c.class_name === name);
  if (!row) throw new Error(`class ${name} not found: ${JSON.stringify(res.data).slice(0, 200)}`);
  return row.id;
}

async function dropClassMappings(typeId) {
  const res = await admin('GET', `/fee/class-mappings/?fee_type_id=${typeId}&limit=500`);
  for (const m of res.data || []) await admin('DELETE', `/fee/class-mappings/${m.id}`);
}

async function dropStudentMappings(studentId) {
  const res = await admin('GET', `/fee/student-mappings/?student_id=${studentId}&limit=500`);
  for (const m of res.data || []) await admin('DELETE', `/fee/student-mappings/${m.id}`);
}

module.exports.classIdByName = classIdByName;
module.exports.dropClassMappings = dropClassMappings;
module.exports.dropStudentMappings = dropStudentMappings;

async function createRefund(txnId, amount, action) {
  const created = must(await admin('POST', '/fee/refunds/', {
    fee_transaction_id: txnId, refund_amount: amount, refund_reason: 'excess_payment', detailed_reason: 'QA refund',
  }), 'refund');
  if (action) must(await admin('POST', '/fee/refunds/approve', { refund_id: created.id, action }), 'approve');
  return created;
}

module.exports.createRefund = createRefund;

async function roleHasGrant(roleName, resource, action) {
  const roles = await admin('GET', '/admin/role-mgmt/roles/');
  const role = roles.data.roles.find((r) => r.name === roleName);
  const rows = await admin('GET', `/auth/resource-permissions/role/${role.id}`);
  return (rows.data || []).some((r) => r.resource === resource && r.action === action && r.is_granted !== false);
}

module.exports.roleHasGrant = roleHasGrant;

async function allTerms() {
  const res = await admin('GET', '/fee/terms/?limit=500&offset=0');
  return res.data || [];
}

async function sharedTerm(name, dates = ['2026-06-15', '2026-10-15', '2027-01-15']) {
  const found = (await allTerms()).find((t) => t.term_name === name);
  if (found) return found;
  const res = await admin('POST', '/fee/terms/', {
    term_name: name, term_status: 'active', number_of_terms: dates.length, academic_year_id: await yearId(),
    fee_term_dates: dates.map((d) => ({ fee_term_date: d })),
  });
  if (res.status === 400) {
    const again = (await allTerms()).find((t) => t.term_name === name);
    if (again) return again;
  }
  return must(res, 'shared term');
}

module.exports.allTerms = allTerms;
module.exports.sharedTerm = sharedTerm;
