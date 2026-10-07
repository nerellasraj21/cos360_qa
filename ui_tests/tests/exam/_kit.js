const { unique } = require('../../helpers/fixtures');

function rows(res) {
  return Array.isArray(res.data) ? res.data : (res.data && (res.data.items || res.data.users)) || [];
}

async function workingYear(api) {
  const res = await api('GET', '/masters/academic_years/?active_only=false&limit=1000');
  return rows(res).find((y) => y.title === '2026-2027');
}

async function subjectIds(api) {
  const res = await api('GET', '/masters/subjects/?limit=1000');
  const map = {};
  for (const s of rows(res)) if (s.is_active && !map[s.name]) map[s.name] = s.id;
  return map;
}

function phone() {
  return '9' + String(Math.floor(Math.random() * 1e9)).padStart(9, '0');
}

async function createQaClass(api, cleanup, subjects = ['Mathematics', 'English', 'Environmental Studies']) {
  const year = await workingYear(api);
  const name = unique('QA Exm');
  const made = await api('POST', '/masters/class_sections/', {
    body: { name, short_code: `X${Date.now().toString(36).slice(-6)}`, academic_year_id: year.id, sections: [{ name: 'A' }] },
  });
  if (made.status !== 201) throw new Error(`class create ${made.status} ${JSON.stringify(made.data)}`);
  const ids = await subjectIds(api);
  const map = await api('POST', '/masters/class-subject-mappings/bulk', {
    body: {
      class_id: made.data.id,
      section_id: made.data.sections[0].id,
      academic_year_id: year.id,
      subjects: subjects.map((s, i) => ({ subject_id: ids[s], order: i + 1 })),
    },
  });
  if (map.status !== 201) throw new Error(`mapping ${map.status} ${JSON.stringify(map.data)}`);
  cleanup(async () => {
    const list = await api('GET', `/masters/class-subject-mappings/?class_id=${made.data.id}&active_only=false&limit=1000`);
    for (const m of list.data.items || []) await api('DELETE', `/masters/class-subject-mappings/${m.id}`);
    await api('DELETE', `/masters/class_sections/${made.data.id}`);
  });
  return { id: made.data.id, name, sectionId: made.data.sections[0].id, sectionName: 'A', year, subjectIds: ids, label: `${name} - A`, dash: `${name} – A` };
}

async function createStudents(api, cleanup, klass, firstNames) {
  const out = [];
  const t = Date.now().toString(36).slice(-5).toUpperCase();
  let i = 0;
  for (const first of firstNames) {
    i += 1;
    const admissionNumber = `QX${t}${i}`;
    const res = await api('POST', '/students/admission/', {
      body: {
        academic_year_id: klass.year.id,
        admitted_class_id: klass.id,
        current_class_id: klass.id,
        current_section_id: klass.sectionId,
        address_line1: 'QA street',
        admission_number: admissionNumber,
        admission_date: '2026-09-01',
        student: {
          first_name: first,
          last_name: 'Qaexm',
          date_of_birth: '2015-01-01',
          gender: 'Male',
          father: { name: `QA Dad ${t}${i}`, phone: phone(), email: `qa.exm.${t}${i}.dad@example.com`, relation_to_student: 'Father' },
          mother: { name: `QA Mom ${t}${i}`, phone: phone(), relation_to_student: 'Mother' },
        },
      },
    });
    if (res.status !== 201) throw new Error(`admission ${res.status} ${JSON.stringify(res.data)}`);
    cleanup(async () => {
      for (const name of [`qa.exm.${t}${i}.dad@example.com`, admissionNumber, `${admissionNumber}.mother`]) {
        const users = await api('GET', `/admin/users/?search=${encodeURIComponent(name)}`);
        const found = rows(users).find((r) => r.username === name);
        if (found) await api('PATCH', `/admin/users/${found.id}`, { body: { is_active: false } });
      }
    });
    cleanup(() => api('DELETE', `/students/admission/${res.data.id}`));
    out.push({ id: res.data.student.id, admissionId: res.data.id, admissionNumber, firstName: first, name: `${first} Qaexm` });
  }
  return out;
}

async function standardScheme(api) {
  const res = await api('GET', '/grade-schemes/exam');
  const list = rows(res);
  return list.find((s) => s.scheme_name === 'Standard Percentage Grading' || s.name === 'Standard Percentage Grading');
}

async function createExam(api, cleanup, klass, opts = {}) {
  const name = opts.name || unique('QA FA1');
  const scheme = await standardScheme(api);
  const subs = opts.subjects || [
    ['Mathematics', [['Written', 80], ['Oral', 20]]],
    ['English', [['Written', 100]]],
    ['Environmental Studies', [['Written', 100]]],
  ];
  const body = {
    exam: {
      exam_name: name,
      board: 'State',
      level: 'primary',
      exam_type: 'Formative',
      nature: 'formative',
      academic_year_id: klass.year.id,
      exam_grade_scheme_id: scheme ? scheme.id : null,
      ...(opts.exam || {}),
    },
    class_sections: [{ class_id: klass.id, section_id: klass.sectionId }],
    subject_configs: subs.map(([s, comps], i) => ({
      class_id: klass.id,
      section_id: klass.sectionId,
      subject_id: klass.subjectIds[s],
      sort_order: i + 1,
      components: comps.map(([c, m], j) => ({ component_name: c, entry_type: 'marks', max_marks: m, sort_order: j + 1 })),
    })),
    exam_dates: opts.dates || [],
  };
  const res = await api('POST', '/exams', { body });
  if (res.status !== 201) throw new Error(`exam create ${res.status} ${JSON.stringify(res.data)}`);
  const exam = { id: res.data.exam_id, name };
  cleanup(async () => {
    const cur = await api('GET', `/exams/${exam.id}`);
    if (cur.status === 200 && cur.data.status === 'published') await api('POST', `/exams/${exam.id}/unlock`, { body: { reason: 'QA cleanup' } });
    await api('DELETE', `/exams/${exam.id}`);
  });
  return exam;
}

async function deleteExamsNamed(api, prefix) {
  const res = await api('GET', '/exams');
  for (const e of rows(res)) {
    if (e.exam_name.startsWith(prefix)) {
      if (e.status === 'published') await api('POST', `/exams/${e.id}/unlock`, { body: { reason: 'QA cleanup' } });
      await api('DELETE', `/exams/${e.id}`);
    }
  }
}

async function pickTime(page, index, hour, minute, period) {
  await page.getByRole('button', { name: /Select time|\d\d:\d\d (AM|PM)/ }).nth(index).click();
  const pop = page.getByRole('dialog').filter({ hasText: 'Hour' });
  await pop.getByRole('button', { name: period, exact: true }).click();
  await pop.getByRole('button', { name: String(hour).padStart(2, '0'), exact: true }).first().click();
  await pop.getByRole('button', { name: String(minute).padStart(2, '0'), exact: true }).last().click();
  await pop.getByRole('button', { name: 'Done' }).click();
}

async function markAttendance(api, cleanup, student, dates, presentCount) {
  for (let i = 0; i < dates.length; i += 1) {
    const res = await api('POST', '/student/attendance/', {
      body: { student_id: student.id, date: dates[i], status: i < presentCount ? 'present' : 'absent' },
    });
    if (res.status !== 201) throw new Error(`attendance ${res.status} ${JSON.stringify(res.data)}`);
    cleanup(() => api('DELETE', `/student/attendance/${res.data.id}`));
  }
}

const ATT_DATES = ['2026-09-28', '2026-09-29', '2026-09-30', '2026-10-01', '2026-10-02'];

async function saveMarks(api, exam, klass, student, byComponentName) {
  const nameOf = Object.fromEntries(Object.entries(klass.subjectIds).map(([n, id]) => [id, n]));
  const cfgs = kit_rows(await api('GET', `/exams/${exam.id}/subject-configs`));
  for (const cfg of cfgs) {
    const marks = [];
    for (const comp of cfg.components) {
      const v = byComponentName[`${nameOf[cfg.subject_id]}:${comp.component_name}`];
      if (v !== undefined) marks.push({ student_id: student.id, component_id: comp.id, marks_obtained: v });
    }
    if (marks.length) {
      const res = await api('POST', `/exams/${exam.id}/marks`, { body: { exam_id: exam.id, subject_config_id: cfg.id, marks } });
      if (res.status >= 300) throw new Error(`marks ${res.status} ${JSON.stringify(res.data)}`);
    }
  }
}
const kit_rows = rows;

module.exports = { markAttendance, ATT_DATES, saveMarks, pickTime, rows, workingYear, subjectIds, createQaClass, createStudents, createExam, deleteExamsNamed, standardScheme, unique };

const mobile = {
  vis: (locator) => locator.locator('visible=true'),
  text: (page, value, options = { exact: true }) => page.getByText(value, options).locator('visible=true'),
  async openHub(page) {
    await page.goto('/exam', { timeout: 180_000 });
    await module.exports.mobile.text(page, 'Exam Management').first().waitFor({ timeout: 60_000 });
  },
  async tile(page, name) {
    await module.exports.mobile.text(page, name).first().click();
  },
};
module.exports.mobile = mobile;
