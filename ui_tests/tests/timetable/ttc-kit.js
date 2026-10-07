const { expect } = require('@playwright/test');
const { login } = require('../../helpers/api');

const TT = '/students/timetable/frontend';
const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];

async function yearId() {
  const data = await login('admin');
  return data.academic_year_id;
}

async function createHoliday(api, cleanup, name, extra = {}) {
  const res = await api('POST', '/masters/holidays/', {
    body: { name, description: 'QA outing', start_date: '2026-10-28', end_date: '2026-10-28', is_active: true, academic_year_id: await yearId(), color: '#2563eb', ...extra },
  });
  expect([200, 201], JSON.stringify(res.data)).toContain(res.status);
  cleanup(async () => { await api('DELETE', `/masters/holidays/${res.data.id}`); });
  return res.data;
}

async function findHoliday(api, name) {
  const res = await api('GET', `/masters/holidays/?limit=1000&active_only=false&academic_year_id=${await yearId()}`);
  return (res.data.items || []).find((h) => h.name === name);
}

async function sectionId(api, label) {
  const res = await api('GET', '/masters/class_sections/class-section-list');
  const found = (res.data || []).find((s) => s.class_section_name === label);
  expect(found, `section ${label}`).toBeTruthy();
  return found.section_id;
}

async function subjectIds(api) {
  const res = await api('GET', '/masters/subjects/dropdown');
  const map = {};
  for (const s of res.data || []) map[s.name] = s.id;
  return map;
}

async function clearTimetable(api, sid) {
  await api('DELETE', `${TT}/${sid}`);
}

async function putTimetable(api, cleanup, sid, rows) {
  await clearTimetable(api, sid);
  const res = await api('POST', TT, { body: { section_id: sid, timetable_data: rows } });
  expect([200, 201], JSON.stringify(res.data)).toContain(res.status);
  cleanup(() => clearTimetable(api, sid));
  return res.data;
}

function subjectRow(from, to, subjectId, days = DAYS) {
  const subjects = {};
  for (const d of days) subjects[d] = subjectId;
  return { time: { from, to }, type: 'subject', subjects };
}

async function getTimetable(api, sid) {
  const res = await api('GET', `${TT}/${sid}`);
  if (res.status !== 200) return null;
  res.data.timetable_data.sort((a, b) => a.time.from.localeCompare(b.time.from));
  return res.data;
}

module.exports = { yearId, createHoliday, findHoliday, sectionId, subjectIds, clearTimetable, putTimetable, subjectRow, getTimetable, DAYS };
