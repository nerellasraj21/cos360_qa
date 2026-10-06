(function () {
'use strict';
var D = window.__DATA__;
var SPEC = D.spec, BESPOKE = D.bespoke, THEMES = D.themes, ICONS = D.icons;
var BY = {};
SPEC.forEach(function (e) {
  if (e.list && !e.list.columns.length) {
    var df = e.detail && e.detail.fields && e.detail.fields.length ? e.detail.fields : null;
    if (df) e.list.columns = df;
    else { e.actions.unshift({ method: e.list.method, path: e.list.path, summary: e.list.summary || 'Read', pathParams: [], query: e.list.filters || [], body: [], contentType: null }); e.list = null; }
  }
  BY[e.tag] = e;
});

/* ---------------------------------------------------------------- helpers */
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function ic(n, sz, st) { sz = sz || 20; return '<svg class="i" viewBox="0 0 24 24" style="width:' + sz + 'px;height:' + sz + 'px;' + (st || '') + '" aria-hidden="true">' + (ICONS[n] || ICONS.info) + '</svg>'; }
var ABBR = { id: 'ID', dob: 'DOB', uan: 'UAN', ifsc: 'IFSC', pf: 'PF', sms: 'SMS', upi: 'UPI', url: 'URL', pdf: 'PDF', ac: 'AC', gst: 'GST', otp: 'OTP', api: 'API', ui: 'UI', hsn: 'HSN', na: 'N/A', qr: 'QR', tc: 'TC' };
function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
function human(k) {
  var w = String(k).replace(/_id$/, '').split('_').filter(Boolean).map(function (x) { return ABBR[x] || x; });
  if (!w.length) return k;
  w[0] = cap(w[0]);
  return w.join(' ');
}
var FIRST = ['Aarav', 'Ananya', 'Diya', 'Ishaan', 'Kabir', 'Meera', 'Rohan', 'Saanvi', 'Vihaan', 'Anika', 'Arjun', 'Isha', 'Neel', 'Tara', 'Yash', 'Zoya'];
var LAST = ['Sharma', 'Reddy', 'Nair', 'Gupta', 'Verma', 'Iyer', 'Das', 'Patel', 'Singh', 'Joshi', 'Rao', 'Kapoor'];
var CITY = ['Hyderabad', 'Pune', 'Bengaluru', 'Chennai', 'Kochi', 'Jaipur'];
var STATE = ['Telangana', 'Maharashtra', 'Karnataka', 'Tamil Nadu', 'Kerala', 'Rajasthan'];
var SUBJ = ['Mathematics', 'Science', 'English', 'Hindi', 'Social Studies', 'Computer Science', 'Telugu', 'Art'];
function pick(a, i) { return a[i % a.length]; }
function person(i) { return pick(FIRST, i) + ' ' + pick(LAST, i * 3 + 1); }
var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
function dstr(i, k) {
  if (/birth|dob/.test(k)) return (2012 + i % 3) + '-0' + (1 + i % 9) + '-1' + (i % 9);
  if (/exp|renewal|inspect|valid|due|deadline|to_date|end/.test(k)) return '2027-0' + (1 + i % 9) + '-15';
  return '2026-0' + (6 + i % 4) + '-' + (10 + i);
}
function fmtDate(s) { var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s); return m ? (+m[3]) + ' ' + MON[+m[2] - 1] + ' ' + m[1] : s; }
function ref(k, i) {
  var s = k.replace(/_id$/, '');
  if (/class/.test(s)) return 'Class ' + (1 + i % 10);
  if (/section/.test(s)) return pick(['A', 'B', 'C'], i);
  if (/academic_year/.test(s)) return '2026-27';
  if (/student/.test(s) || /^user$/.test(s)) return person(i);
  if (/parent|father|mother|guardian/.test(s)) return person(i + 5);
  if (/staff|teacher|driver|employee/.test(s)) return 'Mrs. ' + person(i + 2).split(' ')[1];
  if (/subject/.test(s)) return pick(SUBJ, i);
  if (/route/.test(s)) return 'Route ' + (1 + i % 6);
  if (/vehicle/.test(s)) return 'Bus ' + (1 + i % 6) + ' (KA 01 AB ' + (1200 + i) + ')';
  if (/fee_type/.test(s)) return pick(['Tuition fee', 'Transport fee', 'Activity fee', 'Lab fee'], i);
  if (/fee_term|term/.test(s)) return 'Term ' + (1 + i % 3);
  if (/exam/.test(s)) return pick(['Unit test 1', 'Mid-term', 'Unit test 2', 'Annual'], i);
  if (/role/.test(s)) return pick(['Admin', 'Staff', 'Teacher', 'Student', 'Parent'], i);
  if (/designation/.test(s)) return pick(['Teacher', 'Coordinator', 'Principal', 'Accountant'], i);
  if (/state/.test(s)) return pick(STATE, i);
  if (/district/.test(s)) return pick(CITY, i) + ' district';
  if (/mandal/.test(s)) return pick(CITY, i + 2) + ' mandal';
  if (/caste/.test(s)) return pick(['General', 'OBC', 'SC', 'ST'], i);
  if (/category/.test(s)) return pick(['Academic', 'Co-curricular', 'Transport', 'Admission'], i);
  if (/template/.test(s)) return pick(['Fee reminder', 'Absent alert', 'Result notice'], i);
  if (/trip/.test(s)) return pick(['Morning pickup', 'Evening drop'], i);
  if (/stop/.test(s)) return 'Stop ' + (1 + i % 8);
  if (/certificate/.test(s)) return pick(['Bonafide', 'Transfer certificate', 'Conduct'], i);
  return human(k) + ' ' + (i + 1);
}
function val(f, i) {
  var k = f.key.toLowerCase();
  if (f.enum && f.enum.length) return f.enum[i % f.enum.length];
  if (f.type === 'boolean') return /active|enabled|default|publish|present/.test(k) ? true : i % 3 !== 0;
  if (f.type === 'integer') {
    if (/year/.test(k)) return 2026;
    if (/roll|order|sequence|number$/.test(k) && !/phone|aadhar/.test(k)) return i + 1;
    if (/trip|term|count|number_of|attempt|credit/.test(k)) return 2 + i % 3;
    if (/experience/.test(k)) return 3 + i;
    return 10 + i * 5;
  }
  if (f.type === 'number') {
    if (/percent|attendance/.test(k)) return 75 + i * 3;
    if (/mark|max/.test(k)) return 50;
    if (/min_pass/.test(k)) return 18;
    if (/salary/.test(k)) return 32000 + i * 2500;
    if (/total|amount|fee|price|paid|due|cost|balance/.test(k)) return 4500 + i * 1500;
    return 100 + i * 25;
  }
  if (f.type === 'array' || f.type === 'object') return null;
  if (/(^|_)id$/.test(k)) return ref(k, i);
  if (f.format === 'date-time' || /_at$/.test(k)) return '2026-10-0' + (1 + i % 8) + 'T09:' + (10 + i) + ':00';
  if (f.format === 'date' || /(_date|^date$|_on$|deadline)$/.test(k)) return dstr(i, k);
  if (f.format === 'time' || /(^|_)time$/.test(k)) return i % 2 ? '14:30' : '09:00';
  if (f.format === 'email' || /email/.test(k)) return pick(FIRST, i).toLowerCase() + '.' + pick(LAST, i).toLowerCase() + '@example.com';
  if (/phone|mobile|contact_no|whatsapp/.test(k)) return '98' + (76543210 - i * 1111);
  if (/aadhar|aadhaar/.test(k)) return '4' + (23456789012 + i * 37);
  if (/account_number/.test(k)) return '3201' + (4567890123 + i);
  if (/ifsc/.test(k)) return 'SBIN000' + (1230 + i);
  if (/pincode|pin_code|postal/.test(k)) return '5000' + (10 + i);
  if (/pf_account|uan/.test(k)) return 'UAN' + (1004567890 + i);
  if (/registration/.test(k)) return 'KA 01 AB ' + (1200 + i);
  if (/licence|license/.test(k)) return 'DL-0420' + (1100 + i);
  if (/admission_number|admission_no/.test(k)) return '2026-0' + (400 + i * 7);
  if (/receipt_number|transaction_number/.test(k)) return 'R-' + (20480 + i);
  if (/cheque_number/.test(k)) return '00' + (45120 + i);
  if (/reference|upi_ref/.test(k)) return 'UPI' + (3100200 + i * 17);
  if (/idempotency/.test(k)) return 'idem-' + (7000 + i);
  if (/board/.test(k)) return pick(['CBSE', 'ICSE', 'State board'], i);
  if (/first_name/.test(k)) return pick(FIRST, i);
  if (/(last_name|surname)/.test(k)) return pick(LAST, i * 3 + 1);
  if (/class_name/.test(k)) return 'Class ' + (1 + i % 10);
  if (/section_name/.test(k)) return pick(['A', 'B', 'C'], i);
  if (/subject_name|^subject$/.test(k)) return pick(SUBJ, i);
  if (/exam_name/.test(k)) return pick(['Unit test 1', 'Mid-term 2026', 'Unit test 2', 'Annual 2026'], i);
  if (/route_name/.test(k)) return 'Route ' + (1 + i % 6);
  if (/vehicle_name|bus_name/.test(k)) return 'Bus ' + (1 + i % 6);
  if (/designation/.test(k)) return pick(['Teacher', 'Coordinator', 'Principal'], i);
  if (/department/.test(k)) return pick(['Science', 'Languages', 'Administration', 'Sports'], i);
  if (/driver|co_driver/.test(k)) return person(i + 4);
  if (/(^|_)name$|title/.test(k)) return /school|org|client|tenant/.test(k) ? 'Little Bunny School' : (/category|type|template|term|fee|scheme|pattern|set|board/.test(k) ? pick(['Tuition fee', 'Transport fee', 'Activity fee', 'Lab fee'], i) : person(i));
  if (/address_line1|^address$/.test(k)) return (12 + i) + ', Gandhi Road';
  if (/address_line2/.test(k)) return 'Near City Park';
  if (/city/.test(k)) return pick(CITY, i);
  if (/^state/.test(k)) return pick(STATE, i);
  if (/qualification/.test(k)) return pick(['B.Ed', 'M.Sc', 'M.A.', 'B.Sc'], i);
  if (/nationality/.test(k)) return 'Indian';
  if (/mother_tongue/.test(k)) return pick(['Telugu', 'Hindi', 'Tamil', 'Kannada'], i);
  if (/religion/.test(k)) return pick(['Hindu', 'Muslim', 'Christian', 'Sikh'], i);
  if (/blood/.test(k)) return pick(['A+', 'B+', 'O+', 'AB+'], i);
  if (/gender/.test(k)) return pick(['Male', 'Female'], i);
  if (/occupation/.test(k)) return pick(['Engineer', 'Doctor', 'Shop owner', 'Teacher'], i);
  if (/status/.test(k)) return pick(['active', 'pending', 'completed'], i);
  if (/method/.test(k)) return pick(['cash', 'upi', 'cheque'], i);
  if (/(url|path|photo|file|logo|image|signature)/.test(k)) return '/media/' + k + '/' + (1000 + i) + '.png';
  if (/(remark|note|reason|comment|description|message|body)/.test(k)) return pick(['Paid by father at the counter', 'Parent asked for a receipt copy', 'Reviewed and approved', 'Needs follow-up next week'], i);
  if (/color|colour/.test(k)) return pick(['#B94E28', '#4F46E5', '#1B7F46'], i);
  if (/year/.test(k)) return '2026-27';
  if (/code/.test(k)) return 'C' + (100 + i);
  if (/label/.test(k)) return human(k) + ' ' + (i + 1);
  return human(k) + ' ' + (i + 1);
}
function money(k) { return /amount|fee|salary|total|price|paid|due|cost|balance|refund|concession|discount/.test(String(k).toLowerCase()); }
function tone(v) {
  v = String(v).toLowerCase();
  if (/^(active|paid|present|published|completed|delivered|sent|approved|verified|cleared|issued|eligible|yes|success)/.test(v)) return 'ok';
  if (/^(pending|draft|queued|late|partial|half|processing|scheduled|upcoming)/.test(v)) return 'warn';
  if (/^(absent|failed|overdue|inactive|rejected|bounced|cancelled|blocked|ineligible|expired|leave)/.test(v)) return 'bad';
  return 'mute';
}
function cell(f, v, i) {
  if (v == null) return '<span class="hint">—</span>';
  if (f.type === 'boolean') return '<span class="chip ' + (v ? 'ok' : 'mute') + '">' + (v ? 'Yes' : 'No') + '</span>';
  if (f.enum || /status|method|type$|nature|level|gender/.test(f.key)) return '<span class="chip ' + tone(v) + '">' + esc(v) + '</span>';
  if (typeof v === 'number') return '<span class="num">' + (money(f.key) ? 'Rs ' : '') + v.toLocaleString('en-IN') + '</span>';
  if (/^\d{4}-\d{2}-\d{2}T/.test(v)) return '<span class="num">' + fmtDate(v) + ', ' + v.slice(11, 16) + '</span>';
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return '<span class="num">' + fmtDate(v) + '</span>';
  if (/(^|_)id$/.test(f.key) && f.key !== 'id') return esc(v);
  if (f.key === 'id') return '<span class="mono">' + esc(String(v)) + '</span>';
  return esc(v);
}
function shortId(i) { return ['3f9a', '81c2', 'a7d4', 'c05e', '29bb', 'e61f', '7d30', 'b9a8'][i % 8] + '…' + ['c21b', '04ef', '9e77', '5a10', 'd8c3', '1b92', 'f4a6', '63de'][i % 8]; }

/* ---------------------------------------------------------------- info architecture */
var ROOMS = [
  { id: 'today', label: 'Today', icon: 'grid', secs: [
    { id: 'today', label: 'Today', custom: ['today'], bare: true, desc: 'The school day on one dial, what needs you, and quick actions.' },
    { id: 'me', label: 'My profile', group: 'Account', tag: 'Profile', also: ['Student Profile', 'Staff Profile', 'Parent Profile'], desc: 'Every user can read and update their own profile and change their password.' }
  ] },
  { id: 'people', label: 'People', icon: 'users', secs: [
    { id: 'students', label: 'Students', group: 'Students', tag: 'Student/Student Admission', custom: ['student360'], listFirst: true, desc: 'Admit, find and manage students. Open a student to see everything about them in one 360 view.' },
    { id: 'documents', label: 'Student documents', group: 'Students', tag: 'Student/Student Documents' },
    { id: 'family', label: 'Family links', group: 'Students', tag: 'Student-Parent Associations' },
    { id: 'parents', label: 'Parents', group: 'Parents', tag: 'Parents' },
    { id: 'staff', label: 'Staff', group: 'Staff', tag: 'Staff', desc: 'Enrolment, designations, qualifications, photo, attendance and bulk upload.' },
    { id: 'certtypes', label: 'Certificate types', group: 'Certificates', tag: 'Student/Certificate Types' },
    { id: 'templates', label: 'Certificate templates', group: 'Certificates', tag: 'Student/Issuable Certificates', custom: ['certificate'], listFirst: true },
    { id: 'certs', label: 'Issued and received', group: 'Certificates', tag: 'Student/Student Certificates' }
  ] },
  { id: 'accounts', label: 'Accounts', icon: 'wallet', secs: [
    { id: 'counter', label: 'Counter', group: 'Daily', tag: 'Fee Collection', custom: ['counter'], desc: 'Find a student, choose what is being paid, take the payment and print the receipt.' },
    { id: 'transactions', label: 'Transactions', group: 'Daily', tag: 'Fee/Fee Transactions' },
    { id: 'receipts', label: 'Receipts', group: 'Daily', tag: 'Fee/Fee Receipts' },
    { id: 'refunds', label: 'Refunds', group: 'Daily', tag: 'Fee/Fee Refunds' },
    { id: 'concessions', label: 'Concessions', group: 'Daily', tag: 'Fee Concessions' },
    { id: 'oldfees', label: 'Old fees', group: 'Daily', tag: 'Fee Old Fees' },
    { id: 'terms', label: 'Terms and dates', group: 'Fee setup', tag: 'Fee/Fee Terms & Dates' },
    { id: 'categories', label: 'Categories', group: 'Fee setup', tag: 'Fee/Fee Categories' },
    { id: 'types', label: 'Fee types', group: 'Fee setup', tag: 'Fee/Fee Types' },
    { id: 'classmaps', label: 'Class fees', group: 'Fee setup', tag: 'Fee/Fee Class Mappings' },
    { id: 'termamounts', label: 'Term amounts', group: 'Fee setup', tag: 'Fee/Fee Class Mapping Term Amounts' },
    { id: 'studentmaps', label: 'Student fees', group: 'Fee setup', tag: 'Fee/Fee Student Mappings' },
    { id: 'xcat', label: 'Categories', group: 'Expenses', tag: 'Expense/Expense Categories' },
    { id: 'xdept', label: 'Departments', group: 'Expenses', tag: 'Expense/Expense Departments' },
    { id: 'xtype', label: 'Types', group: 'Expenses', tag: 'Expense/Expense Types' },
    { id: 'xtxn', label: 'Transactions', group: 'Expenses', tag: 'Expense/Expense Transactions' },
    { id: 'xsum', label: 'Summary', group: 'Expenses', tag: 'Expense/Summary' },
    { id: 'xrep', label: 'Reports', group: 'Expenses', tag: 'Expense/Reports' },
    { id: 'xset', label: 'Settings', group: 'Expenses', tag: 'Expense/Settings' },
    { id: 'xaud', label: 'Audit trail', group: 'Expenses', tag: 'Expense/Audit Trail' },
    { id: 'xatt', label: 'Attachments', group: 'Expenses', tag: 'Expense/Attachments' }
  ] },
  { id: 'classes', label: 'Classes', icon: 'book', secs: [
    { id: 'attendance', label: 'Attendance', group: 'Daily', tag: 'Student/Student Attendance', custom: ['classroom'], desc: 'Mark the register on a classroom map. Paint a status, then tap desks.' },
    { id: 'timetable', label: 'Timetable', group: 'Daily', tag: 'Student/Timetable', custom: ['timetable'] },
    { id: 'holidays', label: 'Holidays', group: 'Daily', tag: 'Masters/Holidays' },
    { id: 'years', label: 'Academic years', group: 'Structure', tag: 'Masters/Academic Years' },
    { id: 'classes', label: 'Classes and sections', group: 'Structure', tag: 'Masters/Class & Sections' },
    { id: 'subjects', label: 'Subjects', group: 'Structure', tag: 'Masters/Subjects' },
    { id: 'subcat', label: 'Subject categories', group: 'Structure', tag: 'Masters/SubjectCategories', also: ['Subject Categories'] },
    { id: 'csm', label: 'Class subjects', group: 'Structure', tag: 'Masters/Class Subject Mappings' }
  ] },
  { id: 'exams', label: 'Exams', icon: 'clipboard', secs: [
    { id: 'exams', label: 'Exams', group: 'Run an exam', tag: 'Exams', desc: 'Create an exam in steps: details, classes, subjects with marks components, then dates.' },
    { id: 'dates', label: 'Exam dates', group: 'Run an exam', tag: 'Exam Dates' },
    { id: 'marks', label: 'Mark entry', group: 'Run an exam', tag: 'Mark Entry', custom: ['marks'], desc: 'Enter marks one student at a time, with a live grade and class spread.' },
    { id: 'perms', label: 'Mark permissions', group: 'Run an exam', tag: 'Mark Entry Permissions' },
    { id: 'hall', label: 'Hall tickets', group: 'Run an exam', tag: 'Hall Tickets', custom: ['hall'] },
    { id: 'results', label: 'Results', group: 'Run an exam', tag: 'Exam Results' },
    { id: 'notify', label: 'Notifications', group: 'Run an exam', tag: 'Exam Notifications' },
    { id: 'audit', label: 'Audit log', group: 'Run an exam', tag: 'Exam Audit' },
    { id: 'esettings', label: 'Exam settings', group: 'Setup', tag: 'Exam Settings' },
    { id: 'boards', label: 'Board patterns', group: 'Setup', tag: 'Board Patterns' },
    { id: 'grading', label: 'Grading', group: 'Setup', tag: 'Grading' },
    { id: 'remarks', label: 'Remark grades', group: 'Setup', tag: 'Remark Grades' },
    { id: 'patterns', label: 'Exam patterns', group: 'Setup', tag: 'Exam Patterns' }
  ] },
  { id: 'transport', label: 'Transport', icon: 'bus', secs: [
    { id: 'vehicles', label: 'Vehicles', tag: 'Masters/Vehicles' },
    { id: 'routes', label: 'Routes', tag: 'Masters/Routes' },
    { id: 'stops', label: 'Route stops', tag: 'Masters/Route Stops' },
    { id: 'trips', label: 'Trips', tag: 'Masters/Trips' },
    { id: 'pricing', label: 'Pricing', tag: 'Masters/Transport Pricing' },
    { id: 'rtypes', label: 'Route types', tag: 'Masters/Route Types' },
    { id: 'ttypes', label: 'Trip types', tag: 'Masters/Trip Types' },
    { id: 'stransport', label: 'Student transport', tag: 'Student/Student Transport' }
  ] },
  { id: 'messages', label: 'Messages', icon: 'send', secs: [
    { id: 'comm', label: 'Templates, send and logs', tag: 'Communication', desc: 'Compose from a template, preview the recipient count, send and read the delivery log.' },
    { id: 'announce', label: 'Announcements', tag: 'Announcements' }
  ] },
  { id: 'reports', label: 'Reports', icon: 'chart', secs: [
    { id: 'rstudent', label: 'Students', tag: 'Student Reports' },
    { id: 'rstaff', label: 'Staff', tag: 'Staff Reports' },
    { id: 'rfee', label: 'Fees', tag: 'Fee Reports' },
    { id: 'ratt', label: 'Attendance', tag: 'Attendance Reports' },
    { id: 'rfin', label: 'Financial', tag: 'Financial Reports' },
    { id: 'rgen', label: 'Exports and audit', tag: 'Reports' }
  ] },
  { id: 'setup', label: 'Setup', icon: 'sliders', secs: [
    { id: 'school', label: 'School settings', group: 'School', tag: 'School Settings' },
    { id: 'users', label: 'Users', group: 'Access', tag: 'Tenant Admin/User Management' },
    { id: 'roles', label: 'Roles', group: 'Access', tag: 'Tenant Admin/Role Management', also: ['Auth/Roles'], custom: ['permissions'] },
    { id: 'resperm', label: 'Resource permissions', group: 'Access', tag: 'Auth/Resource Permissions' },
    { id: 'menus', label: 'Menus', group: 'Access', tag: 'Auth/Menus', also: ['Auth/Permissions'] },
    { id: 'login', label: 'Sign in and access', group: 'Access', tag: 'Auth/Login', also: ['Auth/Access Validation'] },
    { id: 'castes', label: 'Castes', group: 'Masters', tag: 'Masters/Castes' },
    { id: 'locations', label: 'Locations', group: 'Masters', tag: 'Masters/Locations' },
    { id: 'orgs', label: 'Organisations', group: 'Platform', tag: 'SuperAdmin Organizations' },
    { id: 'plans', label: 'Plans', group: 'Platform', tag: 'Super Admin/Plan Management' },
    { id: 'tenants', label: 'Tenants', group: 'Platform', tag: 'Super Admin/System Management' },
    { id: 'tdata', label: 'Tenant data access', group: 'Platform', tag: 'Super Admin/Tenant Data Access' },
    { id: 'sauth', label: 'Super admin sign in', group: 'Platform', tag: 'Super Admin/Authentication', also: ['Super Admin/Setup'] },
    { id: 'seed', label: 'Seed data', group: 'Platform', tag: 'Auth/Seed Data', also: ['Other'] }
  ] }
];
var ROOMBAR = ROOMS.filter(function (r) { return r.id !== 'setup'; });

/* ---------------------------------------------------------------- state */
var ST = { room: 'today', sec: 'today', tab: null, device: 'web', theme: 'clay', keys: true, showAll: false, drawer: null, leaf: null, open: {}, menuOpen: false, step: 0, scr: {}, q: '' };

/* ---------------------------------------------------------------- multilevel menu (mirrors the tenant menus table: L0 modules, L1 pages, L2 groups) */
var MENU = [
  ['Dashboard', 'grid', [['Dashboard', 'today.today']]],
  ['Masters', 'sliders', [
    ['Academic Years', 'classes.years'], ['Classes and Sections', 'classes.classes'], ['Subject Categories', 'classes.subcat'], ['Subjects', 'classes.subjects'],
    ['Class Subject Mappings', 'classes.csm'], ['Holidays', 'classes.holidays'], ['Parents', 'people.parents'], ['Castes', 'setup.castes'], ['Locations', 'setup.locations'],
    ['School Registration', 'setup.school'], ['Roles and Permissions', 'setup.roles']]],
  ['Students', 'users', [
    ['Admission', 'people.students'], ['Attendance', 'classes.attendance'], ['Student Documents', 'people.documents'], ['Family Links', 'people.family'], ['Student Transport', 'transport.stransport'],
    ['Certificates', null, [['Issued and Received', 'people.certs'], ['Certificate Types', 'people.certtypes'], ['Certificate Templates', 'people.templates']]]]],
  ['Staff', 'user', [['Enrollment', 'people.staff'], ['Designations', 'people.staff'], ['Staff Attendance', 'people.staff']]],
  ['Fee', 'wallet', [
    ['Collection', null, [['Fee Collection', 'accounts.counter'], ['Fee Receipts', 'accounts.receipts'], ['Fee Transactions', 'accounts.transactions'], ['Fee Refunds', 'accounts.refunds'], ['Concessions', 'accounts.concessions'], ['Old Fees', 'accounts.oldfees']]],
    ['Setup', null, [['Fee Categories', 'accounts.categories'], ['Fee Types', 'accounts.types'], ['Fee Terms', 'accounts.terms'], ['Fee Mappings', 'accounts.classmaps'], ['Term Amounts', 'accounts.termamounts'], ['Student Fees', 'accounts.studentmaps']]],
    ['Fee Reports', 'reports.rfee']]],
  ['Transport', 'bus', [['Routes', 'transport.routes'], ['Route Stops', 'transport.stops'], ['Vehicles', 'transport.vehicles'], ['Trips', 'transport.trips'], ['Pricing', 'transport.pricing'], ['Route Types', 'transport.rtypes'], ['Trip Types', 'transport.ttypes']]],
  ['Exam', 'clipboard', [
    ['Run an exam', null, [['Exams', 'exams.exams'], ['Exam Dates', 'exams.dates'], ['Mark Entry', 'exams.marks'], ['Mark Permissions', 'exams.perms'], ['Hall Tickets', 'exams.hall'], ['Results', 'exams.results'], ['Notifications', 'exams.notify'], ['Exam Audit', 'exams.audit']]],
    ['Setup', null, [['Exam Settings', 'exams.esettings'], ['Board Patterns', 'exams.boards'], ['Grading', 'exams.grading'], ['Remark Grades', 'exams.remarks'], ['Exam Patterns', 'exams.patterns']]]]],
  ['Expense', 'receipt', [
    ['Transactions', 'accounts.xtxn'], ['Summary', 'accounts.xsum'], ['Reports', 'accounts.xrep'], ['Audit Trail', 'accounts.xaud'], ['Attachments', 'accounts.xatt'],
    ['Setup', null, [['Categories', 'accounts.xcat'], ['Departments', 'accounts.xdept'], ['Types', 'accounts.xtype'], ['Settings', 'accounts.xset']]]]],
  ['Communication', 'send', [['Compose, Templates and Logs', 'messages.comm'], ['Announcements', 'messages.announce']]],
  ['Timetable', 'clock', [['Timetable', 'classes.timetable']]],
  ['Calendar', 'calendar', [['Calendar and Holidays', 'classes.holidays']]],
  ['Reports', 'chart', [['Students', 'reports.rstudent'], ['Staff', 'reports.rstaff'], ['Fees', 'reports.rfee'], ['Attendance', 'reports.ratt'], ['Financial', 'reports.rfin'], ['Exports and Audit', 'reports.rgen']]],
  ['Administration', 'shield', [
    ['Users', 'setup.users'], ['School Settings', 'setup.school'], ['Resource Permissions', 'setup.resperm'], ['Menus', 'setup.menus'], ['Sign-in and Access', 'setup.login'],
    ['Platform', null, [['Organisations', 'setup.orgs'], ['Plans', 'setup.plans'], ['Tenants', 'setup.tenants'], ['Tenant Data Access', 'setup.tdata'], ['Super Admin Sign-in', 'setup.sauth'], ['Seed Data', 'setup.seed']]]]]
];
var LEAVES = [];
(function walk(nodes, path) {
  nodes.forEach(function (n) {
    var p = path.concat([n[0]]);
    if (!Array.isArray(n[2])) { LEAVES.push({ key: p.join('/'), go: n[1], path: p }); } else walk(n[2], p);
  });
})(MENU.map(function (m) { return m[2].length === 1 && !Array.isArray(m[2][0][2]) ? [m[0], m[2][0][1]] : m; }), []);
function activeLeaf() {
  var go = ST.room + '.' + ST.sec, hit = null;
  LEAVES.forEach(function (l) { if (l.key === ST.leaf && l.go === go) hit = l; });
  if (!hit) LEAVES.forEach(function (l) { if (!hit && l.go === go) hit = l; });
  return hit;
}
function menuHtml() {
  var act = activeLeaf(), openKey = act ? act.key : '';
  function isOpen(key) { return ST.open[key] !== undefined ? ST.open[key] : openKey.indexOf(key + '/') === 0; }
  function node(n, path, depth) {
    var p = path.concat([n[0]]), key = p.join('/'), kids = Array.isArray(n[2]) ? n[2] : null;
    if (depth === 0 && kids && kids.length === 1 && !Array.isArray(kids[0][2])) { n = [n[0], n[1], null, kids[0][1]]; kids = null; }
    if (!kids) {
      var go = n[3] || n[1], on = act && act.key === key;
      return '<a class="mi l' + depth + (depth === 0 ? ' top' : '') + (on ? ' on' : '') + '" data-act="leaf" data-key="' + esc(key) + '" data-go="' + go + '" role="treeitem" tabindex="0"' + (on ? ' aria-current="page"' : '') + '>' + (depth === 0 ? ic(n[1], 19) : '') + '<span>' + esc(n[0]) + '</span></a>';
    }
    var o = isOpen(key), has = act && act.key.indexOf(key + '/') === 0;
    return '<div class="grp d' + depth + (o ? ' open' : '') + '" role="none"><button class="mi l' + depth + ' top' + (has ? ' has' : '') + '" data-act="fold" data-key="' + esc(key) + '" aria-expanded="' + o + '" role="treeitem">' + (depth === 0 ? ic(n[1], 19) : '') + '<span>' + esc(n[0]) + '</span><i class="chev">' + ic('chevR', 16) + '</i></button>' +
      '<div class="kids" role="group"' + (o ? '' : ' hidden') + '>' + kids.map(function (k) { return node(k, p, depth + 1); }).join('') + '</div></div>';
  }
  return MENU.map(function (n) { return node(n, [], 0); }).join('');
}

var APP, MAIN;
function findRoom(id) { return ROOMS.filter(function (r) { return r.id === id; })[0] || ROOMS[0]; }
function findSec(room, id) { return room.secs.filter(function (s) { return s.id === id; })[0] || room.secs[0]; }
var MERGED = {};
function entry(sec, tag) {
  if (tag) return BY[tag] || null;
  if (MERGED[sec.id] !== undefined) return MERGED[sec.id];
  var base = BY[sec.tag] || null, extra = (sec.also || []).map(function (t) { return BY[t]; }).filter(Boolean);
  if (!base && extra.length) { base = extra.shift(); }
  if (!base) { MERGED[sec.id] = null; return null; }
  var m = {}; Object.keys(base).forEach(function (k) { m[k] = base[k]; });
  m.actions = base.actions.slice(); m.ops = base.ops;
  extra.forEach(function (x) {
    ['list', 'detail', 'create', 'update', 'delete'].forEach(function (k) { if (!m[k] && x[k]) m[k] = x[k]; });
    m.actions = m.actions.concat(x.actions); m.ops += x.ops;
  });
  MERGED[sec.id] = m; return m;
}
function th(html) {
  var m = THEMES[ST.theme]; if (!m || ST.theme === 'base') return html;
  html = html.replace(/#[0-9A-Fa-f]{6}\b/g, function (h) { return m.hex[h.toUpperCase()] || h; });
  Object.keys(m.rgba).forEach(function (o) { html = html.split('rgba(' + o + ',').join('rgba(' + m.rgba[o] + ','); });
  return html;
}
function toast(msg) { var t = document.createElement('div'); t.className = 'toast'; t.textContent = msg; document.body.appendChild(t); setTimeout(function () { t.remove(); }, 2400); }

/* ---------------------------------------------------------------- forms */
var LONG = /(description|remark|note|address(?!_line)|body|message|reason|comment|subjects_dealt|policy)/;
function fid(p, k) { return 'f-' + (p + '-' + k).replace(/[^a-z0-9]+/gi, '-'); }
function kcap(f) { return ST.keys ? '<span class="k">' + esc(f.key) + '</span>' : ''; }
function fieldHtml(f, i, p) {
  var lab = '<label for="' + fid(p, f.key) + '">' + esc(human(f.key)) + (f.required ? '<span class="req" title="Required">*</span>' : '') + kcap(f) + '</label>';
  var help = f.description ? '<div class="help">' + esc(f.description) + '</div>' : '';
  var lim = []; if (f.maxLength) lim.push('max ' + f.maxLength + ' characters'); if (f.minimum != null) lim.push('min ' + f.minimum); if (f.maximum != null) lim.push('max ' + f.maximum);
  if (lim.length) help += '<div class="help">' + lim.join(' · ') + '</div>';
  var id = fid(p, f.key), v = val(f, i), k = f.key.toLowerCase();
  if (f.type === 'object' && f.fields) return '<div class="fs full"><div class="fh"><b>' + esc(human(f.key)) + '</b>' + kcap(f) + (f.required ? '<span class="chip warn">Required</span>' : '') + '</div><div class="formgrid">' + f.fields.map(function (x) { return fieldHtml(x, i, p + '.' + f.key); }).join('') + '</div></div>';
  if (f.type === 'array') {
    if (f.items) {
      var items = [0, 1].map(function (n) { return '<div class="repitem"><div class="chips" style="margin-bottom:12px"><b>' + esc(human(f.key).replace(/s$/, '')) + ' ' + (n + 1) + '</b><span style="margin-left:auto"><button class="btn sm ghost" type="button" data-act="toast" data-msg="Row removed">Remove</button></span></div><div class="formgrid">' + f.items.map(function (x) { return fieldHtml(x, i + n, p + '.' + f.key + n); }).join('') + '</div></div>'; }).join('');
      return '<div class="fs full"><div class="fh"><b>' + esc(human(f.key)) + '</b>' + kcap(f) + (f.required ? '<span class="chip warn">At least one</span>' : '') + '</div><div class="rep">' + items + '<button class="btn" type="button" data-act="toast" data-msg="Row added">' + ic('plus', 18) + 'Add ' + esc(human(f.key).toLowerCase().replace(/s$/, '')) + '</button></div></div>';
    }
    var tags = f.enum ? f.enum.slice(0, 2) : [pick(SUBJ, i), pick(SUBJ, i + 1), pick(SUBJ, i + 2)];
    return '<div class="fld full">' + lab + '<div class="tagin">' + tags.map(function (t) { return '<span class="chip">' + esc(t) + ' ✕</span>'; }).join('') + '<span class="hint">Type and press Enter</span></div>' + help + '</div>';
  }
  if (f.type === 'boolean') return '<div class="fld">' + lab.replace('<label', '<label style="margin-bottom:0"') + '<span class="sw' + (v ? ' on' : '') + '" data-sw="1" role="switch" tabindex="0" aria-checked="' + (!!v) + '" id="' + id + '"><span class="track"></span><span>' + (v ? 'On' : 'Off') + '</span></span>' + help + '</div>';
  if (f.enum && f.enum.length) {
    if (f.enum.length <= 4) return '<div class="fld"><label>' + esc(human(f.key)) + (f.required ? '<span class="req">*</span>' : '') + kcap(f) + '</label><div class="seg" role="radiogroup">' + f.enum.map(function (o) { return '<span data-pick="1" class="' + (o === v ? 'on' : '') + '" role="radio" tabindex="0">' + esc(o) + '</span>'; }).join('') + '</div>' + help + '</div>';
    return '<div class="fld">' + lab + '<select class="inp" id="' + id + '">' + f.enum.map(function (o) { return '<option' + (o === v ? ' selected' : '') + '>' + esc(o) + '</option>'; }).join('') + '</select>' + help + '</div>';
  }
  if (/(^|_)id$/.test(k)) return '<div class="fld">' + lab + '<select class="inp" id="' + id + '">' + [0, 1, 2, 3].map(function (n) { return '<option' + (n === 0 ? ' selected' : '') + '>' + esc(ref(k, i + n)) + '</option>'; }).join('') + '</select>' + help + '</div>';
  if (f.format === 'binary' || /(^file$|photo|logo|signature|upload)/.test(k)) return '<div class="fld full">' + lab + '<div class="drop">' + ic('upload', 26) + '<div style="margin-top:6px">Drop a file here or choose one</div></div>' + help + '</div>';
  if (LONG.test(k) && f.type === 'string') return '<div class="fld full">' + lab + '<textarea class="inp" id="' + id + '">' + esc(v) + '</textarea>' + help + '</div>';
  var type = 'text';
  if (f.format === 'date-time' || /_at$/.test(k)) { type = 'datetime-local'; v = String(v).slice(0, 16); }
  else if (f.format === 'date' || /(_date|^date$|deadline)$/.test(k)) type = 'date';
  else if (f.format === 'time' || /(^|_)time$/.test(k)) type = 'time';
  else if (f.type === 'integer' || f.type === 'number') type = 'number';
  else if (/email/.test(k)) type = 'email';
  else if (/phone|mobile/.test(k)) type = 'tel';
  else if (/password/.test(k)) { type = 'password'; v = 'Sample#2026'; }
  if (f.type === 'string' && f.enum == null && /^(string)$/.test(f.type) && false) type = 'text';
  return '<div class="fld">' + lab + '<input class="inp' + (type === 'number' ? ' num' : '') + '" id="' + id + '" type="' + type + '" value="' + esc(v) + '"' + (f.maxLength ? ' maxlength="' + f.maxLength + '"' : '') + '>' + help + '</div>';
}
function formHtml(fields, i, p) { return '<div class="formgrid">' + fields.map(function (f) { return fieldHtml(f, i || 0, p || 'f'); }).join('') + '</div>'; }
function fieldKeys(f) { return f.map(function (x) { return x.key; }); }

/* ---------------------------------------------------------------- generic tabs */
function titleOf(tag) { return tag.split('/').pop(); }
function opChip(m, p) { return '<span class="m ' + m + '">' + m + '</span> <span class="mono" style="font-size:12.5px;color:var(--muted)">' + esc(p.replace('/api/v1', '')) + '</span>'; }
function visibleCols(cols, all) {
  var c = cols.filter(function (x) { return x.type !== 'array' && x.type !== 'object'; });
  if (all) return cols;
  var named = c.filter(function (x) { return !/(^id$|_id$|created_at|updated_at|tenant)/.test(x.key); });
  return named.slice(0, 7);
}
function rowsFor(cols, n) { var rows = []; for (var i = 0; i < n; i++) { var r = {}; cols.forEach(function (f) { r[f.key] = f.key === 'id' ? shortId(i) : val(f, i); }); rows.push(r); } return rows; }
function listTab(e) {
  var L = e.list;
  if (!L) return '<div class="panel empty">' + ic('info', 28) + '<p>This group has no list endpoint. Use the Actions tab.</p></div>';
  var cols = visibleCols(L.columns, ST.showAll), rows = rowsFor(L.columns, 8);
  var q = ST.q.toLowerCase();
  if (q) rows = rows.filter(function (r) { return JSON.stringify(r).toLowerCase().indexOf(q) > -1; });
  var head = '<tr>' + cols.map(function (c) { return '<th' + (typeof val(c, 0) === 'number' ? ' class="r"' : '') + '>' + esc(human(c.key)) + '<span class="k">' + esc(c.key) + '</span></th>'; }).join('') + '<th></th></tr>';
  var body = rows.map(function (r, n) { return '<tr class="row" data-row="' + n + '">' + cols.map(function (c) { return '<td' + (typeof r[c.key] === 'number' ? ' class="r"' : '') + '>' + cell(c, r[c.key], n) + '</td>'; }).join('') + '<td class="r"><button class="btn sm ghost" aria-label="Row actions" data-row="' + n + '">' + ic('more', 18) + '</button></td></tr>'; }).join('');
  var flt = (L.filters || []).filter(function (f) { return !/^(page|page_size|skip|limit|offset|sort|order)/.test(f.key); }).slice(0, 4);
  return '<section class="panel" style="overflow:hidden"><div class="toolbar" style="padding:16px 18px;border-bottom:1px solid var(--line)"><label class="search" style="flex:1 1 260px;max-width:380px">' + ic('search') + '<input id="q" placeholder="Search this list" value="' + esc(ST.q) + '"></label>' +
    flt.map(function (f) { return '<span class="pill">' + esc(human(f.key)) + (f.enum ? ': All' : '') + ic('chevD', 15) + '</span>'; }).join('') +
    '<button class="btn" data-act="toggleCols" style="margin-left:auto">' + (ST.showAll ? 'Show fewer fields' : 'Show all ' + L.columns.length + ' fields') + '</button>' +
    (e.create ? '<button class="btn pri" data-act="tab" data-tab="create">' + ic('plus', 18) + 'New ' + esc(titleOf(e.tag).toLowerCase().replace(/s$/, '')) + '</button>' : '') + '</div>' +
    '<div class="tablewrap"><table class="tbl"><thead>' + head + '</thead><tbody>' + (body || '<tr><td colspan="9" class="empty">No rows match that search.</td></tr>') + '</tbody></table></div>' +
    '<div class="pager"><span class="hint num">1 to ' + rows.length + ' of 128</span><span style="margin-left:auto;display:flex;gap:8px;align-items:center"><button class="btn sm" disabled aria-label="Previous page">' + ic('chevL', 18) + '</button><span class="num" style="font-weight:700;font-size:14px">Page 1 of 16</span><button class="btn sm" aria-label="Next page">' + ic('chevR', 18) + '</button></span></div></section>' +
    '<div class="hint" style="padding:0 6px">Data shown is sample data. Columns and filters are the real fields of <span class="mono">' + esc(opChip(L.method, L.path).replace(/<[^>]+>/g, '')) + '</span>.</div>';
}
function wizardSteps(e, c) {
  if (e.tag === 'Student/Student Admission') {
    var f = {}; c.fields.forEach(function (x) { f[x.key] = x; });
    var stu = f.student || { fields: [] };
    var sf = {}; (stu.fields || []).forEach(function (x) { sf[x.key] = x; });
    var scal = (stu.fields || []).filter(function (x) { return x.type !== 'object'; });
    return [
      { label: 'Admission', fields: ['admission_type', 'admission_date', 'academic_year_id', 'admitted_academic_year_id', 'admitted_class_id', 'admitted_section_id', 'current_class_id', 'current_section_id', 'admission_number', 'roll_no'].map(function (k) { return f[k]; }).filter(Boolean) },
      { label: 'Student', fields: scal },
      { label: 'Parents', fields: ['father', 'mother', 'guardian'].map(function (k) { return sf[k]; }).filter(Boolean) },
      { label: 'Address and school', fields: ['address_line1', 'address_line2', 'city', 'state', 'state_id', 'district_id', 'mandal_id', 'is_previous_school', 'previous_school_name', 'previous_class', 'previous_school_remark'].map(function (k) { return f[k]; }).filter(Boolean) },
      { label: 'Review', review: true }
    ];
  }
  var scalars = c.fields.filter(function (x) { return x.type !== 'object' && x.type !== 'array'; });
  var steps = [];
  if (scalars.length) steps.push({ label: 'Details', fields: scalars });
  c.fields.filter(function (x) { return x.type === 'object' || x.type === 'array'; }).forEach(function (x) {
    if (x.type === 'object' && x.fields) steps.push({ label: human(x.key), fields: x.fields }); else steps.push({ label: human(x.key), fields: [x] });
  });
  steps.push({ label: 'Review', review: true });
  return steps;
}
function createTab(e, mode) {
  var c = mode === 'edit' ? (e.update || e.create) : e.create;
  if (!c || !c.fields.length) return '<div class="panel empty">' + ic('info', 28) + '<p>There is no ' + (mode === 'edit' ? 'update' : 'create') + ' form for this group. Use the Actions tab for what it offers.</p></div>';
  var big = c.fields.length > 16 || c.fields.some(function (x) { return x.type === 'object' || x.type === 'array'; });
  var head = '<div class="chips">' + opChip(c.method, mode === 'edit' && c.path ? c.path : c.path) + (c.contentType && /multipart/.test(c.contentType) ? '<span class="chip info">Sends a file</span>' : '') + '</div>';
  var q = c.query && c.query.length ? '<section class="panel" style="padding:20px"><div class="eyebrow" style="margin-bottom:12px">Also sent as query parameters</div>' + formHtml(c.query.map(function (x) { return { key: x.key, type: x.type, format: x.format, required: x.required, enum: x.enum }; }), 0, 'q') + '</section>' : '';
  var i0 = mode === 'edit' ? 2 : 0;
  var save = '<div class="sticky"><span class="hint" style="font-weight:600">' + (mode === 'edit' ? 'Editing the selected row. Changes save to the same record.' : 'Required fields are marked *.') + '</span><span style="margin-left:auto;display:flex;gap:10px"><button class="btn" data-act="tab" data-tab="list">Cancel</button><button class="btn pri" data-act="toast" data-msg="Saved. The new row would appear in the list.">' + (mode === 'edit' ? 'Save changes' : 'Create') + '</button></span></div>';
  if (!big) return head + '<section class="panel" style="padding:26px">' + formHtml(c.fields, i0, mode) + '</section>' + q + save;
  var steps = wizardSteps(e, c), cur = Math.min(ST.step, steps.length - 1);
  var st = '<div class="stepper">' + steps.map(function (s, n) { return '<span class="st ' + (n === cur ? 'on' : n < cur ? 'done' : '') + '" data-act="step" data-n="' + n + '"><i>' + (n < cur ? '✓' : n + 1) + '</i>' + esc(s.label) + '</span>'; }).join('') + '</div>';
  var s = steps[cur], body;
  if (s.review) body = '<section class="panel" style="padding:26px"><h2 class="hero" style="font-size:26px;margin-bottom:6px">Review</h2><p class="sub" style="margin:0 0 18px">Check what will be sent. Nothing is saved until you confirm.</p><dl class="kv">' + steps.filter(function (x) { return !x.review; }).map(function (x) { return '<dt>' + esc(x.label) + '</dt><dd>' + x.fields.slice(0, 6).map(function (f) { return esc(human(f.key)) + ': <span style="color:var(--muted)">' + esc(val(f, i0) == null ? '…' : val(f, i0)) + '</span>'; }).join(' · ') + (x.fields.length > 6 ? ' <span class="hint">+' + (x.fields.length - 6) + ' more</span>' : '') + '</dd>'; }).join('') + '</dl></section>';
  else body = '<section class="panel" style="padding:26px">' + formHtml(s.fields, i0, 'w' + cur) + '</section>';
  var nav = '<div class="sticky"><span class="hint num" style="font-weight:700">Step ' + (cur + 1) + ' of ' + steps.length + '</span><span style="margin-left:auto;display:flex;gap:10px">' + (cur > 0 ? '<button class="btn" data-act="step" data-n="' + (cur - 1) + '">Back</button>' : '') + (cur < steps.length - 1 ? '<button class="btn pri" data-act="step" data-n="' + (cur + 1) + '">Continue</button>' : '<button class="btn pri" data-act="toast" data-msg="Saved. The new record would appear in the list.">' + (mode === 'edit' ? 'Save changes' : 'Create') + '</button>') + '</span></div>';
  return head + st + body + q + nav;
}
function detailTab(e) {
  var L = e.list; if (!L) return '<div class="panel empty">' + ic('info', 28) + '<p>No list to pick a record from.</p></div>';
  var rows = rowsFor(L.columns, 3), r = rows[0];
  var rel = e.actions.filter(function (a) { return /\{/.test(a.path) && a.method === 'GET'; }).slice(0, 5);
  return '<div class="cols2" data-grid2><section class="panel" style="padding:26px"><div class="chips" style="margin-bottom:6px">' + (e.detail ? opChip(e.detail.method, e.detail.path) : '') + '</div><h2 class="hero" style="font-size:26px;margin-bottom:16px">' + esc(String(r[(L.columns.filter(function (c) { return /name|title|number|label/.test(c.key); })[0] || L.columns[0]).key] || 'Record')) + '</h2>' +
    '<dl class="kv">' + L.columns.map(function (c) { return '<dt>' + esc(human(c.key)) + (ST.keys ? '<div class="mono" style="font-weight:500;font-size:11px;color:#9a978c">' + esc(c.key) + '</div>' : '') + '</dt><dd>' + (c.type === 'array' ? '<span class="chip mute">' + (2 + 1) + ' items</span>' : c.type === 'object' ? '<span class="chip mute">Details</span>' : cell(c, r[c.key], 0)) + '</dd>'; }).join('') + '</dl></section>' +
    '<div style="display:flex;flex-direction:column;gap:22px"><section class="panel" style="padding:22px"><div class="eyebrow" style="margin-bottom:12px">Do something with this record</div><div style="display:flex;gap:10px;flex-wrap:wrap">' + (e.update ? '<button class="btn pri" data-act="tab" data-tab="edit">' + ic('edit', 18) + 'Edit</button>' : '') + (e.delete ? '<button class="btn bad" data-act="confirmDelete">Delete</button>' : '') + '<button class="btn" data-act="toast" data-msg="Shared as a link">Copy link</button></div></section>' +
    (rel.length ? '<section class="panel" style="padding:22px"><div class="eyebrow" style="margin-bottom:12px">Related</div>' + rel.map(function (a) { return '<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid var(--line-2)">' + opChip(a.method, a.path) + '</div>'; }).join('') + '</section>' : '') + '</div></div>';
}
function actionBody(a) {
  var f = [];
  a.pathParams.forEach(function (p) { f.push({ key: p.key, type: p.type, required: true }); });
  a.query.forEach(function (p) { f.push({ key: p.key, type: p.type, format: p.format, required: p.required, enum: p.enum }); });
  a.body.forEach(function (b) { f.push(b); });
  return f;
}
function actionsTab(e) {
  if (!e.actions.length) return '<div class="panel empty">' + ic('info', 28) + '<p>No other actions in this group. Everything is on the List, Create and Edit tabs.</p></div>';
  var open = ST.scr.openAction;
  return '<div class="hint" style="padding:0 6px">Every other thing this part of the app can do. Open one to see its inputs.</div>' +
    '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,420px),1fr));gap:16px" data-grid2>' + e.actions.map(function (a, n) {
      var isOpen = open === n, f = actionBody(a);
      return '<section class="panel apicard"><div class="chips"><span class="m ' + a.method + '">' + a.method + '</span><span class="hint" style="font-weight:600">' + esc(a.summary) + '</span></div><div class="path">' + esc(a.path.replace('/api/v1', '')) + '</div>' +
        (isOpen ? (f.length ? formHtml(f, n, 'a' + n) : '<div class="hint">No inputs. It runs straight away.</div>') + '<div style="display:flex;gap:10px"><button class="btn pri sm" data-act="toast" data-msg="Done (design preview)">' + (a.method === 'GET' ? 'Show result' : 'Run') + '</button><button class="btn sm" data-act="openAction" data-n="-1">Close</button></div>' : '<div><button class="btn sm" data-act="openAction" data-n="' + n + '">' + (f.length ? 'Open form (' + f.length + ' inputs)' : 'Open') + '</button></div>') + '</section>';
    }).join('') + '</div>';
}
function apiTab(e) {
  var rows = [];
  function add(x, role) { if (x) rows.push([x.method, x.path, x.summary || role, role]); }
  add(e.list, 'List'); add(e.detail, 'Detail'); add(e.create, 'Create'); add(e.update, 'Update'); add(e.delete, 'Delete');
  e.actions.forEach(function (a) { rows.push([a.method, a.path, a.summary, 'Action']); });
  return '<section class="panel" style="overflow:hidden"><div class="tablewrap"><table class="tbl"><thead><tr><th>Method</th><th>Path</th><th>What it does</th><th>Used for</th></tr></thead><tbody>' + rows.map(function (r) { return '<tr><td><span class="m ' + r[0] + '">' + r[0] + '</span></td><td class="mono">' + esc(r[1].replace('/api/v1', '')) + '</td><td>' + esc(r[2] || '') + '</td><td><span class="chip mute">' + r[3] + '</span></td></tr>'; }).join('') + '</tbody></table></div></section>';
}

/* ---------------------------------------------------------------- designed screens */
function T(html) { return th(html); }
var STATUS = ['present', 'absent', 'late', 'half_day', 'leave'];
var STCOL = { present: 'var(--brand)', absent: 'var(--bad)', late: 'var(--gold)', half_day: '#E9B59B', leave: '#8E8C84' };
function pcard(inner, st) { return '<section class="panel" style="padding:24px;' + (st || '') + '">' + inner + '</section>'; }

function screenCounter() {
  var C = ST.scr.counter = ST.scr.counter || { items: [true, true, false], method: 'cash', stu: 0 };
  var due = [['Tuition fee', 'Term 2', 12000, '30 Sep', 'bad'], ['Transport fee', 'Route 4, Term 2', 4500, '30 Sep', 'bad'], ['Activity fee', 'Term 2', 2000, '15 Oct', 'warn']];
  var sel = due.filter(function (d, n) { return C.items[n]; }), tot = sel.reduce(function (a, d) { return a + d[2]; }, 0), conc = sel.length ? 500 : 0, pay = tot - conc;
  var students = [['Aarav Sharma', '2026-0412', 'Class 7 B', 18500], ['Meera Iyer', '2026-0198', 'Class 4 A', 8200], ['Kabir Verma', '2026-0733', 'Class 9 C', 21000]];
  var s = students[C.stu];
  var rows = due.map(function (d, n) { return '<div style="display:flex;align-items:center;gap:14px;padding:16px 0;border-top:1px dashed #D6D3C6"><input type="checkbox" data-act="dueToggle" data-n="' + n + '" ' + (C.items[n] ? 'checked' : '') + ' aria-label="Select ' + d[0] + '" style="width:22px;height:22px;accent-color:var(--brand)"><div style="flex:1"><b>' + d[0] + '</b><div style="font-size:13px;font-weight:600;color:var(--' + d[4] + ')">' + d[1] + ' · due ' + d[3] + '</div></div><b class="num" style="font-size:17px">Rs ' + d[2].toLocaleString('en-IN') + '</b></div>'; }).join('');
  var mf = { cash: [], upi: [{ key: 'upi_app_name', type: 'string', enum: ['GPay', 'PhonePe', 'Paytm', 'BHIM', 'Other'] }, { key: 'upi_reference', type: 'string' }], cheque: [{ key: 'cheque_number', type: 'string' }, { key: 'cheque_date', type: 'string', format: 'date' }, { key: 'cheque_bank', type: 'string' }], bank_transfer: [{ key: 'bank_name', type: 'string' }, { key: 'bank_reference', type: 'string' }] }[C.method];
  var payload = { student_id: s[0].toLowerCase().replace(' ', '-'), student_admission_num: s[1], academic_year_id: '2026-27', total_amount: pay, payment_method: C.method };
  mf.forEach(function (f) { payload[f.key] = val(f, 0); }); payload.remarks = ''; payload.transaction_items = sel.map(function (d) { return { fee_type_id: d[0], term_date_id: d[1], amount_due: d[2], amount_paid: d[2] }; });
  var slip = '<div class="slip"><div style="display:flex;justify-content:space-between;align-items:center"><b style="font-family:var(--f-display);font-size:18px">vartul.</b><span class="eyebrow">Draft receipt</span></div><div class="dash" style="margin:14px 0"></div><div style="font-size:13.5px;color:var(--muted);line-height:1.6">Receipt no. <b style="color:var(--ink)">R-20482</b><br>Mon 5 Oct 2026<br>' + s[0] + ' · ' + s[1] + ' · ' + s[2] + '</div><div class="dash" style="margin:14px 0 8px"></div>' +
    (sel.map(function (d) { return '<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:15px"><span>' + d[0] + ', ' + d[1].split(', ').pop() + '</span><b>Rs ' + d[2].toLocaleString('en-IN') + '</b></div>'; }).join('') || '<div class="hint" style="padding:8px 0">Tick a fee to add it.</div>') +
    (conc ? '<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:15px;color:var(--ok)"><span>Sibling concession</span><b>- Rs 500</b></div>' : '') + '<div class="dash" style="margin:10px 0 14px"></div><div style="display:flex;justify-content:space-between;align-items:baseline"><span style="font-family:var(--f-display);font-weight:700;font-size:18px">Total received</span><span class="hero num" style="font-size:36px">Rs ' + pay.toLocaleString('en-IN') + '</span></div><div style="display:flex;justify-content:space-between;font-size:13.5px;color:var(--muted);margin-top:6px"><span>Balance after this</span><b style="color:var(--ink)">Rs ' + Math.max(s[3] - pay, 0).toLocaleString('en-IN') + '</b></div><div style="margin-top:18px;text-align:center"><span class="stamp" style="opacity:.25">PAID</span></div></div>';
  return '<label class="search" style="flex:none;max-width:700px;width:100%;background:#fff;border:1.5px solid #D6D3C6;min-height:60px;border-radius:99px;padding:0 24px">' + ic('search', 24) + '<input placeholder="Who is paying? Name, admission number or phone" style="font-size:17px"><span class="kbd">/</span></label>' +
    '<div class="chips">' + students.map(function (x, n) { return '<span class="pill' + (n === C.stu ? ' on' : '') + '" data-act="stu" data-n="' + n + '" role="button" tabindex="0">' + x[0] + ' · ' + x[2] + '</span>'; }).join('') + '</div>' +
    '<div style="display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:26px;align-items:start" data-grid2><div style="display:flex;flex-direction:column;gap:20px">' +
    pcard('<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap"><span class="avatar" style="width:60px;height:60px;font-size:20px">' + s[0].split(' ').map(function (w) { return w[0]; }).join('') + '</span><div style="flex:1 1 200px"><div class="hero" style="font-size:26px">' + s[0] + '</div><div class="hint" style="margin-top:4px">' + s[1] + ' · ' + s[2] + '</div></div><div style="text-align:right"><div class="eyebrow">Total due</div><div class="hero num" style="font-size:32px;color:var(--bad)">Rs ' + s[3].toLocaleString('en-IN') + '</div></div></div>') +
    pcard('<div class="eyebrow" style="margin-bottom:6px">What is being paid ' + (ST.keys ? '<span class="mono" style="text-transform:none;letter-spacing:0;font-weight:600;color:#9a978c">transaction_items</span>' : '') + '</div>' + rows.replace('border-top:1px dashed #D6D3C6', 'border-top:0')) +
    '</div><aside style="display:flex;flex-direction:column;gap:16px">' + slip +
    '<div class="seg">' + ['cash', 'upi', 'cheque', 'bank_transfer'].map(function (m) { return '<span data-act="method" data-m="' + m + '" class="' + (m === C.method ? 'on' : '') + '" role="button" tabindex="0">' + human(m) + '</span>'; }).join('') + '</div>' +
    (mf.length ? '<div class="panel" style="padding:20px">' + formHtml(mf, 0, 'm' + C.method) + '</div>' : '') +
    '<label class="fld"><label>Amount received' + (ST.keys ? '<span class="k">total_amount</span>' : '') + '</label><input class="inp num" value="Rs ' + pay.toLocaleString('en-IN') + '" style="min-height:58px;font-weight:800;font-size:22px;border-radius:18px"></label>' +
    '<label class="fld"><label>Note on the receipt' + (ST.keys ? '<span class="k">remarks</span>' : '') + '</label><input class="inp" placeholder="For example, paid by father"></label>' +
    '<button class="btn pri lg" style="min-height:60px;border-radius:99px;font-size:17px" data-act="toast" data-msg="Receipt R-20482 saved. Printing now." ' + (sel.length ? '' : 'disabled') + '>Collect Rs ' + pay.toLocaleString('en-IN') + ' and print receipt</button>' +
    '<details class="panel" style="padding:16px 20px"><summary style="font-weight:700;cursor:pointer">Request this sends <span class="mono hint">POST /fee/transactions/</span></summary><pre class="mono" style="font-size:12px;overflow:auto;margin:12px 0 0">' + esc(JSON.stringify(payload, null, 2)) + '</pre></details></aside></div>';
}
function screenClassroom() {
  var A = ST.scr.att = ST.scr.att || { brush: 'present', st: {}, n: 30 };
  var names = ['Aarav', 'Ananya', 'Diya', 'Ishaan', 'Kabir', 'Meera', 'Rohan', 'Saanvi', 'Vihaan', 'Anika', 'Arjun', 'Isha', 'Neel', 'Tara', 'Yash', 'Zoya', 'Aditya', 'Bhavna', 'Chirag', 'Dhruv', 'Esha', 'Farhan', 'Gauri', 'Harsh', 'Ira', 'Jay', 'Kiara', 'Laksh', 'Mira', 'Nikhil'];
  if (!A.init) { A.init = 1; [[2, 'absent'], [5, 'late'], [16, 'absent'], [24, 'absent'], [8, 'half_day']].forEach(function (p) { A.st[p[0]] = p[1]; }); for (var q = 0; q < 28; q++) if (!A.st[q] && q !== 27) A.st[q] = 'present'; }
  var cnt = {}, un = 0; STATUS.forEach(function (s) { cnt[s] = 0; });
  names.forEach(function (n, i) { var s = A.st[i]; if (s) cnt[s]++; else un++; });
  var marked = names.length - un;
  var seats = names.map(function (n, i) { var s = A.st[i] || 'u'; var cls = s === 'absent' ? 'a' : s === 'late' || s === 'half_day' ? 'l' : s === 'leave' ? 'u' : s === 'u' ? 'u' : ''; var lab = A.st[i] ? human(A.st[i]) : 'Not marked'; return '<div class="seat ' + cls + '" data-act="seat" data-n="' + i + '" role="button" tabindex="0" aria-label="' + n + ', ' + lab + '"><div class="face">' + n.slice(0, 2) + '</div><div class="nm">' + n + '</div><div class="rl num">' + String(i + 1).padStart(2, '0') + '</div><div class="rl" style="color:' + (STCOL[A.st[i]] || '#8E8C84') + '">' + lab + '</div></div>'; }).join('');
  var abs = names.map(function (n, i) { return [n, i]; }).filter(function (x) { return A.st[x[1]] === 'absent'; });
  var pct = Math.round(marked / names.length * 100);
  var ringHtml = '<div style="position:relative;width:128px;height:128px;flex:none"><svg width="128" height="128" viewBox="0 0 128 128" style="transform:rotate(-90deg)"><circle cx="64" cy="64" r="56" fill="none" stroke="var(--line-2)" stroke-width="14"/><circle cx="64" cy="64" r="56" fill="none" stroke="var(--brand)" stroke-width="14" stroke-linecap="round" stroke-dasharray="' + (2 * Math.PI * 56 * pct / 100).toFixed(1) + ' 400"/></svg><div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center"><b class="hero num" style="font-size:28px">' + marked + '</b><span class="hint" style="font-size:11.5px;font-weight:700">of ' + names.length + ' marked</span></div></div>';
  return '<div class="chips" style="gap:10px"><span class="pill">Class 7 B' + ic('chevD', 15) + '</span><span class="pill">Mon 5 Oct 2026' + ic('calendar', 16) + '</span><span class="chip mute" style="padding:6px 12px">' + (ST.keys ? 'status · date · student_id · remarks' : 'One register per day') + '</span></div>' +
    '<div class="panel" style="padding:14px 18px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><b>Paint with</b><div class="seg" style="flex-wrap:wrap">' + STATUS.map(function (s) { return '<span data-act="brush" data-s="' + s + '" class="' + (A.brush === s ? 'on' : '') + '" role="button" tabindex="0" style="' + (A.brush === s ? 'box-shadow:inset 0 -3px 0 ' + STCOL[s] + ',0 1px 2px rgba(20,20,19,.14)' : '') + '">' + human(s) + '</span>'; }).join('') + '</div><button class="btn sm" data-act="markAll" style="margin-left:auto">' + ic('check', 17) + 'Mark the rest ' + human(A.brush).toLowerCase() + '</button></div>' +
    '<div style="display:grid;grid-template-columns:minmax(0,1.9fr) minmax(0,1fr);gap:26px;align-items:start" data-grid2><section class="panel" style="padding:26px"><div style="background:var(--deep);color:#fff;border-radius:16px;padding:14px 20px;display:flex;align-items:center;gap:12px;margin-bottom:22px"><span style="width:12px;height:12px;border-radius:50%;background:var(--gold)"></span><b style="font-family:var(--f-display);font-size:17px">Board</b><span style="margin-left:auto;color:#B0AEA5;font-weight:600;font-size:14px">Mrs. Nair, class teacher</span></div><div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:12px">' + seats + '</div></section>' +
    '<aside style="display:flex;flex-direction:column;gap:20px"><section class="panel" style="padding:24px;display:flex;gap:20px;align-items:center;flex-wrap:wrap">' + ringHtml + '<div style="display:flex;flex-direction:column;gap:6px;flex:1 1 130px">' + STATUS.map(function (s) { return '<span class="chip ' + (s === 'present' ? 'ok' : s === 'absent' ? 'bad' : s === 'late' || s === 'half_day' ? 'warn' : 'mute') + '" style="width:max-content">' + cnt[s] + ' ' + human(s).toLowerCase() + '</span>'; }).join('') + '</div></section>' +
    '<section class="panel" style="padding:22px"><div class="eyebrow" style="margin-bottom:8px">Absent today</div>' + (abs.map(function (x) { return '<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-top:1px solid var(--line-2)"><span class="avatar" style="width:36px;height:36px;font-size:13px;background:var(--bad-soft);color:var(--bad)">' + x[0].slice(0, 2) + '</span><b style="flex:1">' + x[0] + '</b><input class="inp" placeholder="remarks" aria-label="Remarks for ' + x[0] + '" style="min-height:38px;max-width:150px;font-size:13px"></div>'; }).join('') || '<div class="hint">Nobody is absent.</div>') + '<div class="hint" style="margin-top:10px">Parents of absent students get a message at 10 am.</div></section>' +
    '<button class="btn pri lg" style="border-radius:99px;min-height:58px" data-act="toast" data-msg="Attendance for ' + marked + ' students saved.">Save attendance</button></aside></div>';
}
function screenMarks() {
  var M = ST.scr.marks = ST.scr.marks || { cur: 5, v: { 0: 38, 1: 44, 2: 62, 3: 'AB', 4: 31 } };
  var names = ['Aarav Sharma', 'Ananya Reddy', 'Diya Nair', 'Ishaan Gupta', 'Kabir Verma', 'Meera Iyer', 'Rohan Das', 'Saanvi Patel'];
  var max = 50;
  function grade(p) { return p >= 90 ? 'A+' : p >= 80 ? 'A' : p >= 70 ? 'B+' : p >= 60 ? 'B' : p >= 45 ? 'C' : p >= 33 ? 'D' : 'E'; }
  var entered = Object.keys(M.v).filter(function (k) { return M.v[k] !== '' && M.v[k] != null; }).length;
  var cur = M.cur, cv = M.v[cur];
  var isAb = cv === 'AB', num = parseFloat(cv), bad = !isAb && !isNaN(num) && (num > max || num < 0), has = !isAb && !isNaN(num) && !bad;
  var pct = has ? num / max * 100 : 0;
  var q = names.map(function (n, i) { var v = M.v[i], isC = i === cur, b = v !== 'AB' && !isNaN(parseFloat(v)) && parseFloat(v) > max; return '<div data-act="qpick" data-n="' + i + '" role="button" tabindex="0" style="display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:16px;cursor:pointer;' + (isC ? 'background:var(--deep);color:#fff' : b ? 'background:var(--bad-soft)' : '') + '"><span class="num" style="width:24px;font-size:13px;opacity:.7">' + String(i + 1).padStart(2, '0') + '</span><b style="flex:1;font-size:15px">' + n + '</b>' + (isC ? '<span style="color:var(--gold);font-weight:800">Entering</span>' : b ? '<span style="color:var(--bad);font-weight:800">' + v + ' is over ' + max + '</span>' : v === 'AB' ? '<span class="chip mute">Absent</span>' : v == null || v === '' ? '<span class="hint">Not entered</span>' : '<b class="num" style="color:var(--ok)">' + v + '</b>') + '</div>'; }).join('');
  var bins = [0, 0, 0, 0, 0]; Object.keys(M.v).forEach(function (k) { var x = parseFloat(M.v[k]); if (!isNaN(x) && x <= max) bins[Math.min(4, Math.floor(x / 10))]++; });
  var bx = Math.max.apply(null, bins.concat([1])), cb = has ? Math.min(4, Math.floor(num / 10)) : -1;
  var hist = bins.map(function (b, i) { return '<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:6px"><div style="width:100%;height:' + Math.max(6, Math.round(b / bx * 100)) + 'px;border-radius:10px 10px 4px 4px;background:' + (i === cb ? 'var(--gold)' : '#F0D3C4') + '"></div><span style="font-size:12px;color:var(--muted);font-weight:600">' + ['0-9', '10-19', '20-29', '30-39', '40-50'][i] + '</span></div>'; }).join('');
  var ringc = 2 * Math.PI * 64;
  return '<div class="chips"><span class="chip warn" style="font-size:14px;padding:6px 14px">' + ic('clock', 15) + 'Closes Wednesday 7 Oct</span><span class="chip ok" style="font-size:14px;padding:6px 14px">' + ic('check', 15) + 'Saved just now</span><span class="chip mute" style="padding:6px 12px">' + (ST.keys ? 'marks[] · student_id · component_id · marks_obtained · is_absent · remark_grade' : 'Mid-term · Science · Class 8 B') + '</span></div>' +
    '<div style="display:grid;grid-template-columns:260px minmax(0,1fr) 300px;gap:24px;align-items:start" data-grid2><section class="panel" style="padding:14px;display:flex;flex-direction:column;gap:4px">' + q + '</section>' +
    '<section class="panel" style="padding:34px 38px;display:flex;flex-direction:column;gap:24px"><div style="display:flex;align-items:center;gap:18px"><span class="avatar" style="width:84px;height:84px;font-size:30px;background:var(--gold-soft);color:var(--gold-ink)">' + names[cur].split(' ').map(function (w) { return w[0]; }).join('') + '</span><div><div class="eyebrow">Roll ' + String(cur + 1).padStart(2, '0') + ' · Class 8 B · Science (component: Theory)</div><div class="hero" style="font-size:38px;margin-top:6px">' + names[cur] + '</div></div></div>' +
    '<div style="display:flex;align-items:center;gap:36px;flex-wrap:wrap"><label style="display:flex;flex-direction:column;gap:8px"><span class="eyebrow">Marks out of ' + max + (ST.keys ? ' <span class="mono" style="text-transform:none;letter-spacing:0;color:#9a978c">marks_obtained</span>' : '') + '</span><span style="display:flex;align-items:baseline;gap:12px;border-bottom:4px solid ' + (bad ? 'var(--bad)' : 'var(--brand)') + ';padding-bottom:6px"><input id="markinput" class="num" placeholder="--" value="' + esc(cv == null ? '' : cv) + '" aria-label="Marks obtained" aria-invalid="' + bad + '" style="width:190px;border:0;outline:0;background:transparent;font:800 100px var(--f-display);letter-spacing:-.04em;color:var(--ink)"><span class="hero" style="font-size:34px;color:var(--muted)">/ ' + max + '</span></span>' + (bad ? '<span class="hint err">Enter marks between 0 and ' + max + '.</span>' : '') + '</label>' +
    '<div style="position:relative;width:148px;height:148px;flex:none"><svg width="148" height="148" viewBox="0 0 148 148" style="transform:rotate(-90deg)"><circle cx="74" cy="74" r="64" fill="none" stroke="var(--line-2)" stroke-width="14"/><circle cx="74" cy="74" r="64" fill="none" stroke="' + (bad ? 'var(--bad)' : 'var(--brand)') + '" stroke-width="14" stroke-linecap="round" stroke-dasharray="' + (ringc * (has ? pct : 0) / 100).toFixed(1) + ' 500"/></svg><div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center"><span class="eyebrow" style="font-size:11px">Grade' + (ST.keys ? '' : '') + '</span><b class="hero" style="font-size:48px;color:var(--brand-d)">' + (has ? grade(pct) : isAb ? 'AB' : '–') + '</b></div></div></div>' +
    '<label class="fld"><label>Remark for the report card <span class="hint" style="font-weight:500">Optional</span>' + (ST.keys ? '<span class="k">remark_grade</span>' : '') + '</label><input class="inp" placeholder="For example, strong practical work" style="min-height:54px;font-size:16px"></label>' +
    '<div style="display:flex;gap:12px;flex-wrap:wrap;align-items:center"><button class="btn lg" data-act="markAbsent">Absent <span class="kbd">A</span></button><button class="btn lg" data-act="markNext">Skip</button><button class="btn pri lg" style="margin-left:auto;min-width:230px" data-act="markNext"' + (bad ? ' disabled' : '') + '>Save and next <span class="kbd" style="background:rgba(255,255,255,.2);border-color:transparent;color:#fff">Enter</span></button></div></section>' +
    '<aside style="display:flex;flex-direction:column;gap:20px"><section class="panel" style="padding:22px;display:flex;gap:18px;align-items:center"><div style="position:relative;width:104px;height:104px;flex:none"><svg width="104" height="104" viewBox="0 0 104 104" style="transform:rotate(-90deg)"><circle cx="52" cy="52" r="44" fill="none" stroke="var(--line-2)" stroke-width="12"/><circle cx="52" cy="52" r="44" fill="none" stroke="var(--gold)" stroke-width="12" stroke-linecap="round" stroke-dasharray="' + (2 * Math.PI * 44 * entered / names.length).toFixed(1) + ' 400"/></svg><div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center"><b class="hero num" style="font-size:26px">' + entered + '</b><span style="font-size:11px;color:var(--muted);font-weight:700">of ' + names.length + '</span></div></div><div style="font-size:14.5px;color:var(--ink-2);line-height:1.6"><b style="color:var(--ink)">' + (names.length - entered) + '</b> still empty</div></section>' +
    '<section class="panel" style="padding:22px"><div class="eyebrow" style="margin-bottom:14px">How the class is doing</div><div style="display:flex;align-items:flex-end;gap:8px;height:130px">' + hist + '</div></section><div class="hint" style="padding:0 6px">Marks lock when you submit. An admin can unlock them.</div></aside></div>';
}
function screenTimetable() {
  var days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
  var times = [['08:30', '09:15'], ['09:15', '10:00'], ['10:00', '10:45'], ['10:45', '11:00'], ['11:00', '11:45'], ['11:45', '12:30'], ['12:30', '13:15'], ['13:15', '14:00']];
  var subs = ['Mathematics', 'Science', 'English', 'Hindi', 'Social Studies', 'Computer Science', 'Telugu', 'Art'], cl = ['a', 'b', 'c', ''];
  var g = '<div class="ttgrid"><div></div>' + days.map(function (d) { return '<div class="th">' + d + '</div>'; }).join('');
  times.forEach(function (t, r) {
    g += '<div class="th num" style="padding-top:18px">' + t[0] + '<br>' + t[1] + '</div>';
    days.forEach(function (d, c) { if (r === 3) { g += c === 0 ? '<div class="slot brk" style="grid-column:2 / span 5">Break</div>' : ''; return; } if (r === 6 && c === 0) { g += '<div class="slot brk" style="grid-column:2 / span 5">Lunch</div>'; return; } if (r === 6) return; var s = subs[(r * 2 + c * 3) % subs.length]; g += '<div class="slot ' + cl[(r + c) % 4] + '" data-act="toast" data-msg="Slot edited" role="button" tabindex="0">' + s + '<small>Mrs. ' + LAST[(r + c) % LAST.length] + '</small></div>'; });
  });
  return '<div class="chips"><span class="pill">Class 7 B' + ic('chevD', 15) + '</span><span class="chip mute" style="padding:6px 12px">' + (ST.keys ? 'section_id · slot_time_data[] · day · slot_time_id · subject_options[] · is_break · break_label' : 'One timetable per section') + '</span><button class="btn pri" style="margin-left:auto" data-act="toast" data-msg="Timetable saved">Save timetable</button></div><section class="panel" style="padding:22px;overflow:auto">' + g + '</div></section><div class="hint" style="padding:0 6px">Tap a slot to change its subject or mark it a break. Slot times are set per section.</div>';
}
function screenHall() {
  var rows = ['Aarav Sharma', 'Ananya Reddy', 'Diya Nair', 'Ishaan Gupta', 'Kabir Verma', 'Meera Iyer'].map(function (n, i) { var ok = i !== 2 && i !== 4; return '<tr><td><b>' + n + '</b><div class="hint">Class 10 A · ' + (2026 + '-0' + (310 + i * 9)) + '</div></td><td class="num">' + [96, 91, 68, 88, 74, 94][i] + '%</td><td class="num">Rs ' + [0, 0, 4500, 0, 12000, 0][i].toLocaleString('en-IN') + '</td><td><span class="chip ' + (ok ? 'ok' : 'bad') + '"><span class="dot"></span>' + (ok ? 'Eligible' : 'Not eligible') + '</span></td><td>' + (ok ? '<span class="mono hint">HT-2026-' + (1100 + i) + '</span>' : '<button class="btn sm" data-act="toast" data-msg="Override saved">Override</button>') + '</td></tr>'; }).join('');
  return '<div class="chips"><span class="pill">Class 10 practice exam' + ic('chevD', 15) + '</span><span class="chip mute" style="padding:6px 12px">' + (ST.keys ? 'attendance_override · fee_override · hall_ticket_min_attendance' : 'Eligibility from attendance and fees') + '</span><button class="btn" style="margin-left:auto" data-act="toast" data-msg="Eligibility recomputed">Recompute</button><button class="btn pri" data-act="toast" data-msg="Hall tickets published to 118 students">Publish to students</button></div>' +
    '<div class="cols2" data-grid2 style="align-items:start"><section class="panel" style="overflow:hidden"><div class="tablewrap"><table class="tbl"><thead><tr><th>Student</th><th>Attendance</th><th>Fees due</th><th>Eligibility</th><th>Ticket</th></tr></thead><tbody>' + rows + '</tbody></table></div></section>' +
    '<section class="panel" style="padding:0;overflow:hidden"><div style="background:var(--deep);color:#fff;padding:18px 24px;display:flex;align-items:center;gap:12px"><b style="font-family:var(--f-display);font-size:20px">vartul.</b><span style="margin-left:auto;color:#B0AEA5;font-weight:700">HALL TICKET</span></div><div style="padding:24px"><div style="display:flex;gap:16px;align-items:center"><span class="avatar" style="width:64px;height:64px;font-size:22px">AS</span><div><div class="hero" style="font-size:24px">Aarav Sharma</div><div class="hint">Class 10 A · Admission 2026-0310 · Ticket HT-2026-1100</div></div></div><div class="dash" style="margin:18px 0"></div><table class="tbl" style="margin:0 -16px;width:calc(100% + 32px)"><thead><tr><th>Date</th><th>Subject</th><th>Time</th><th>Venue</th></tr></thead><tbody><tr><td class="num">12 Oct</td><td>Mathematics</td><td class="num">09:30 to 11:00</td><td>Hall A</td></tr><tr><td class="num">14 Oct</td><td>Science</td><td class="num">09:30 to 11:00</td><td>Hall A</td></tr><tr><td class="num">16 Oct</td><td>English</td><td class="num">09:30 to 11:00</td><td>Hall B</td></tr></tbody></table></div></section></div>';
}
function screenCert() {
  return '<div class="cols2" data-grid2 style="align-items:start"><section class="panel" style="padding:26px"><div class="eyebrow" style="margin-bottom:12px">Generate</div>' + formHtml([{ key: 'certificate_type_id', type: 'string', required: true }, { key: 'student_id', type: 'string', required: true }, { key: 'issue_date', type: 'string', format: 'date' }, { key: 'remarks', type: 'string' }], 0, 'cert') + '<div style="display:flex;gap:10px;margin-top:20px"><button class="btn pri" data-act="toast" data-msg="Certificate generated as a PDF">Generate PDF</button><button class="btn" data-act="toast" data-msg="Copy link saved">Copy link</button></div></section>' +
    '<section class="panel" style="padding:34px 38px;border:1.5px solid var(--line);text-align:center"><div style="font-family:var(--f-display);font-weight:800;font-size:15px;letter-spacing:.2em;color:var(--muted)">LITTLE BUNNY SCHOOL</div><div class="hero" style="font-size:34px;margin:14px 0 4px">Bonafide Certificate</div><div class="hint" style="margin-bottom:22px">Certificate no. BC/2026/0148 · Issued 5 Oct 2026</div><p style="font-size:17px;line-height:1.8;text-align:left;margin:0">This is to certify that <b>Aarav Sharma</b>, son of <b>Rakesh Sharma</b>, Admission No. <b>2026-0412</b>, is a bonafide student of Class <b>7 B</b> in this school for the academic year <b>2026-27</b>. His conduct and character are good.</p><div style="display:flex;justify-content:space-between;margin-top:46px;font-weight:700"><span>Class teacher</span><span>Principal</span></div></section></div>';
}
function screenPerms() {
  var P = ST.scr.perm = ST.scr.perm || {};
  var roles = ['Admin', 'Staff', 'Teacher', 'Student', 'Parent'];
  var res = [['students', ['create', 'read', 'list', 'update', 'delete']], ['fee_transactions', ['create', 'read', 'list']], ['fee_receipts', ['read', 'list']], ['exams', ['create', 'read', 'list', 'update', 'delete']], ['exam_marks', ['create', 'read']], ['student_attendance', ['create', 'read', 'list']], ['communications', ['create', 'list']], ['staff', ['create', 'read', 'list', 'update']]];
  var base = { Admin: 1, Staff: 0.7, Teacher: 0.45, Student: 0.15, Parent: 0.2 };
  var rows = '';
  res.forEach(function (r, ri) { r[1].forEach(function (a, ai) { rows += '<tr><td><b>' + r[0] + '</b> <span class="mono hint">' + a + '</span></td>' + roles.map(function (ro, ci) { var key = r[0] + a + ro; var on = key in P ? P[key] : ((ri * 7 + ai * 3 + ci * 5) % 10) / 10 < base[ro]; return '<td><span class="cell ' + (on ? 'y' : '') + '" data-act="perm" data-k="' + key + '" role="checkbox" aria-checked="' + on + '" tabindex="0">✓</span></td>'; }).join('') + '</tr>'; }); });
  return '<div class="chips"><span class="chip mute" style="padding:6px 12px">' + (ST.keys ? 'role_id · resource · action · is_granted' : 'Roles and what they can do') + '</span><button class="btn pri" style="margin-left:auto" data-act="toast" data-msg="Permissions saved">Save changes</button></div><section class="panel" style="overflow:hidden"><div class="tablewrap"><table class="tbl matrix"><thead><tr><th>Resource and action</th>' + roles.map(function (r) { return '<th>' + r + '</th>'; }).join('') + '</tr></thead><tbody>' + rows + '</tbody></table></div></section>';
}
function screenCommand() {
  return '<div class="panel" style="padding:30px;display:flex;flex-direction:column;gap:14px;align-items:flex-start"><h2 class="hero" style="font-size:28px">Type what you want to do</h2><p class="sub" style="margin:0">Press <span class="kbd">Ctrl K</span> anywhere, or use the bar at the top. It searches every screen, and every "New …" form.</p><button class="btn pri lg" data-act="palette">' + ic('search', 20) + 'Open the command bar</button></div>';
}

var CUSTOM = {
  today: { label: 'Today', render: function () { return T(BESPOKE.today); } },
  student360: { label: 'Student 360', render: function () { return T(BESPOKE.student360); } },
  admission: { label: 'Admit a student', render: function () { var e = BY['Student/Student Admission']; return createTab(e, 'create'); } },
  counter: { label: 'Counter', render: screenCounter },
  classroom: { label: 'Classroom', render: screenClassroom },
  marks: { label: 'Marks entry', render: screenMarks },
  timetable: { label: 'Timetable grid', render: screenTimetable },
  hall: { label: 'Hall tickets', render: screenHall },
  certificate: { label: 'Certificate', render: screenCert },
  permissions: { label: 'Permissions', render: screenPerms }
};

/* ---------------------------------------------------------------- render */
function tabsFor(sec) {
  var cust = (sec.custom || []).map(function (c) { return { id: 'c:' + c, label: CUSTOM[c].label, star: true }; });
  var tabs = sec.listFirst ? [] : cust.slice();
  var e = entry(sec);
  if (e) {
    if (e.list) tabs.push({ id: 'list', label: 'List' });
    if (sec.listFirst) tabs = tabs.concat(cust);
    if (e.create) tabs.push({ id: 'create', label: 'Create' });
    if (e.update) tabs.push({ id: 'edit', label: 'Edit' });
    if (e.list) tabs.push({ id: 'detail', label: 'Details' });
    if (e.actions.length) tabs.push({ id: 'actions', label: 'Actions (' + e.actions.length + ')' });
    tabs.push({ id: 'api', label: 'API (' + e.ops + ')' });
  } else if (sec.listFirst) tabs = cust;
  return tabs;
}
function bodyFor(sec, tab) {
  var e = entry(sec);
  if (tab.indexOf('c:') === 0) return CUSTOM[tab.slice(2)].render();
  if (!e) return '<div class="panel empty">Nothing to show.</div>';
  if (tab === 'list') return listTab(e);
  if (tab === 'create') return createTab(e, 'create');
  if (tab === 'edit') return createTab(e, 'edit');
  if (tab === 'detail') return detailTab(e);
  if (tab === 'actions') return actionsTab(e);
  return apiTab(e);
}
function render() {
  var room = findRoom(ST.room), sec = findSec(room, ST.sec);
  var tabs = tabsFor(sec);
  if (!ST.tab || !tabs.some(function (t) { return t.id === ST.tab; })) ST.tab = tabs[0].id;
  var act = activeLeaf();
  var crumb = act ? act.path.join(' / ') : room.label + ' / ' + sec.label;
  var bar = '<header class="roombar"><button class="btn sm hamb" aria-label="Open menu" data-act="menu" style="width:44px;min-height:44px;padding:0;border-radius:50%;background:rgba(255,255,255,.1);border-color:transparent;color:#fff">' + ic('menu', 20) + '</button><div style="padding-right:6px;cursor:pointer" data-act="go" data-go="today.today">' + D.logo + '</div><div style="margin-left:auto;display:flex;align-items:center;gap:12px;flex-wrap:wrap"><div class="cmd" data-act="palette" role="button" tabindex="0">' + ic('search', 19) + '<span style="flex:1">Search or type a command</span><span class="kbd">Ctrl K</span></div><button aria-label="Notifications" class="btn sm" style="width:44px;min-height:44px;padding:0;border-radius:50%;background:rgba(255,255,255,.1);border-color:transparent;color:#fff;position:relative">' + ic('bell', 19) + '<span style="position:absolute;top:9px;right:11px;width:9px;height:9px;border-radius:50%;background:var(--gold);border:2px solid var(--deep)"></span></button><button aria-label="My profile" class="avatar" data-act="go" data-go="today.me" style="width:44px;height:44px;background:var(--gold);color:var(--ink);border:0;cursor:pointer">A</button></div></header>';
  var rail = '<div class="railhead"><span class="eyebrow">Menu</span><button class="btn sm ghost closem" data-act="menu" aria-label="Close menu">' + ic('close', 18) + '</button></div><div role="tree" aria-label="Main menu">' + menuHtml() + '</div>';
  var e = entry(sec);
  var head = '<div><div class="crumbs">' + esc(crumb) + '</div><h1 class="title" style="margin-top:10px">' + esc(act ? act.path[act.path.length - 1] : sec.label) + '</h1>' + (sec.desc ? '<div class="sub">' + esc(sec.desc) + '</div>' : e ? '<div class="sub">' + e.ops + ' operations: ' + [e.list && 'list', e.detail && 'details', e.create && 'create', e.update && 'edit', e.delete && 'delete', e.actions.length && e.actions.length + ' more'].filter(Boolean).join(', ') + '.</div>' : '') + '</div>';
  var tb = '<div class="tabbar" role="tablist">' + tabs.map(function (t) { return '<button role="tab" data-act="tab" data-tab="' + t.id + '" class="' + (t.id === ST.tab ? 'on' : '') + '">' + esc(t.label) + (t.star ? '<span class="star" title="Designed screen"></span>' : '') + '</button>'; }).join('') + '</div>';
  var quick = [['grid', 'Home', 'today.today'], ['users', 'Students', 'people.students'], ['wallet', 'Collect', 'accounts.counter'], ['book', 'Attend', 'classes.attendance']];
  var dock = '<nav class="dockbar" aria-label="Quick">' + quick.map(function (q) { return '<a data-act="go" data-go="' + q[2] + '" class="' + (q[2] === room.id + '.' + sec.id ? 'on' : '') + '" role="button" tabindex="0">' + ic(q[0], 20) + q[1] + '</a>'; }).join('') + '<a data-act="menu" role="button" tabindex="0">' + ic('menu', 20) + 'Menu</a></nav>';
  APP.innerHTML = bar + '<div class="workspace' + (ST.menuOpen ? ' menuopen' : '') + '"><nav class="rail" aria-label="Menu">' + rail + '</nav><div class="mscrim" data-act="menu"></div><main class="main" id="main">' + (sec.bare ? '' : head) + (tabs.length > 1 && !sec.bare ? tb : '') + '<div id="body" class="' + (ST.keys ? '' : 'hidekeys') + '" style="display:flex;flex-direction:column;gap:22px">' + bodyFor(sec, ST.tab) + '</div></main></div>' + dock;
  try { history.replaceState(null, '', '#' + room.id + '.' + sec.id); } catch (er) { /* ignore */ }
  if (ST.drawer != null) drawer();
  var inp = document.getElementById('markinput'); if (inp && ST.focusMark) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); ST.focusMark = false; }
  var qi = document.getElementById('q'); if (qi && ST.focusQ) { qi.focus(); qi.setSelectionRange(qi.value.length, qi.value.length); ST.focusQ = false; }
}
function drawer() {
  var room = findRoom(ST.room), sec = findSec(room, ST.sec), e = entry(sec); if (!e || !e.list) return;
  var r = rowsFor(e.list.columns, 8)[ST.drawer];
  var d = document.createElement('div'); d.id = 'drawerwrap';
  d.innerHTML = '<div class="scrim" data-act="closeDrawer"></div><aside class="drawer" role="dialog" aria-label="Record details"><div class="dh"><h2 class="hero" style="font-size:22px;flex:1">' + esc(String(r[(e.list.columns.filter(function (c) { return /name|title|number|label/.test(c.key); })[0] || e.list.columns[0]).key])) + '</h2><button class="btn sm ghost" data-act="closeDrawer" aria-label="Close">' + ic('close', 20) + '</button></div><div class="db"><dl class="kv">' + e.list.columns.filter(function (c) { return c.type !== 'array' && c.type !== 'object'; }).map(function (c) { return '<dt>' + esc(human(c.key)) + '</dt><dd>' + cell(c, r[c.key], ST.drawer) + '</dd>'; }).join('') + '</dl><div style="display:flex;gap:10px;flex-wrap:wrap">' + (e.update ? '<button class="btn pri" data-act="editRow">' + ic('edit', 18) + 'Edit</button>' : '') + (e.delete ? '<button class="btn bad" data-act="confirmDelete">Delete</button>' : '') + '</div></div></aside>';
  APP.appendChild(d);
}
function palette() {
  var items = [];
  ROOMS.forEach(function (r) { r.secs.forEach(function (s) { var e = entry(s); items.push({ t: 'Go to ' + s.label, s: r.label, room: r.id, sec: s.id, icon: 'chevR' }); if (e && e.create) items.push({ t: 'New ' + titleOf(e.tag).toLowerCase().replace(/s$/, ''), s: r.label + ' · ' + s.label, room: r.id, sec: s.id, tab: 'create', icon: 'plus' }); }); });
  var w = document.createElement('div'); w.id = 'pal';
  w.innerHTML = '<div class="scrim" data-act="closePal" style="z-index:70"></div><div style="position:fixed;left:50%;top:90px;transform:translateX(-50%);width:min(680px,94vw);background:#fff;border-radius:28px;z-index:71;box-shadow:0 40px 90px -30px rgba(0,0,0,.6);overflow:hidden"><div style="display:flex;align-items:center;gap:14px;padding:20px 24px;border-bottom:1px solid var(--line)">' + ic('search', 24, 'color:var(--brand)') + '<input id="palq" autocomplete="off" placeholder="Type a screen or an action, for example: new student" style="border:0;outline:0;flex:1;font:700 22px var(--f-display);background:transparent;color:var(--ink)"><span class="kbd">Esc</span></div><div id="palr" style="max-height:52vh;overflow:auto;padding:10px"></div><div style="padding:12px 24px;background:#FAF9F5;border-top:1px solid var(--line);font-size:13px;color:var(--muted);font-weight:600"><span class="kbd">↑</span> <span class="kbd">↓</span> move · <span class="kbd">Enter</span> open · ' + items.length + ' places</div></div>';
  document.body.appendChild(w);
  var q = w.querySelector('#palq'), res = w.querySelector('#palr'), sel = 0, list = [];
  function paint() {
    var t = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    list = items.filter(function (x) { var s = (x.t + ' ' + x.s).toLowerCase(); return t.every(function (z) { return s.indexOf(z) > -1; }); }).slice(0, 40);
    if (sel >= list.length) sel = 0;
    res.innerHTML = list.map(function (x, n) { return '<div data-i="' + n + '" role="option" style="display:flex;align-items:center;gap:12px;padding:11px 14px;border-radius:14px;cursor:pointer;' + (n === sel ? 'background:var(--brand-soft)' : '') + '"><span style="width:34px;height:34px;border-radius:50%;background:var(--line-2);display:flex;align-items:center;justify-content:center;color:var(--ink-2)">' + ic(x.icon, 17) + '</span><div style="flex:1;min-width:0"><b>' + esc(x.t) + '</b><div class="hint" style="font-size:12.5px">' + esc(x.s) + '</div></div></div>'; }).join('') || '<div class="empty">Nothing matches.</div>';
  }
  function go(n) { var x = list[n]; if (!x) return; close(); nav(x.room, x.sec, x.tab); }
  function close() { w.remove(); document.removeEventListener('keydown', kd, true); }
  function kd(ev) { if (ev.key === 'Escape') { close(); } else if (ev.key === 'ArrowDown') { sel = Math.min(sel + 1, list.length - 1); paint(); ev.preventDefault(); } else if (ev.key === 'ArrowUp') { sel = Math.max(sel - 1, 0); paint(); ev.preventDefault(); } else if (ev.key === 'Enter') { go(sel); ev.preventDefault(); } }
  document.addEventListener('keydown', kd, true);
  q.addEventListener('input', function () { sel = 0; paint(); });
  w.addEventListener('click', function (ev) { var r = ev.target.closest('[data-i]'); if (r) go(+r.getAttribute('data-i')); if (ev.target.getAttribute('data-act') === 'closePal') close(); });
  paint(); q.focus();
}
function nav(room, sec, tab) { ST.room = room; ST.sec = sec; ST.tab = tab || null; ST.step = 0; ST.q = ''; ST.drawer = null; ST.showAll = false; var d = document.getElementById('drawerwrap'); if (d) d.remove(); render(); var s = document.scrollingElement; if (s && ST.device === 'web') s.scrollTop = 0; }
function setTheme(name) {
  ST.theme = name;
  document.getElementById('css-clay').disabled = name !== 'clay';
  document.getElementById('css-spectrum').disabled = name !== 'spectrum';
}
function layout() {
  var stage = document.getElementById('stage'), frame = document.getElementById('frame');
  stage.className = ST.device === 'phone' ? 'phone' : '';
  var w = ST.device === 'phone' ? 370 : frame.clientWidth;
  APP.classList.toggle('narrow', w < 820);
}
function tools() {
  var t = document.getElementById('tools');
  t.innerHTML = '<div class="seg"><button data-tool="web" class="' + (ST.device === 'web' ? 'on' : '') + '">Web</button><button data-tool="phone" class="' + (ST.device === 'phone' ? 'on' : '') + '">Phone</button></div><div class="seg"><button data-tool="clay" class="' + (ST.theme === 'clay' ? 'on' : '') + '">Clay</button><button data-tool="spectrum" class="' + (ST.theme === 'spectrum' ? 'on' : '') + '">Spectrum</button></div><div class="seg"><button data-tool="keys" class="' + (ST.keys ? 'on' : '') + '">API field names</button></div>';
}
function delegate(ev) {
  var t = ev.target;
  var sw = t.closest('[data-sw]'); if (sw && ev.type === 'click') { var on = !sw.classList.contains('on'); sw.classList.toggle('on', on); sw.setAttribute('aria-checked', on); sw.lastChild.textContent = on ? 'On' : 'Off'; return; }
  var pk = t.closest('[data-pick]'); if (pk && ev.type === 'click') { Array.prototype.forEach.call(pk.parentNode.children, function (c) { c.classList.remove('on'); }); pk.classList.add('on'); return; }
  var tr = t.closest('tr.row,button[data-row]'); if (tr && !t.closest('[data-act]') && ev.type === 'click') { ST.drawer = +tr.getAttribute('data-row'); render(); return; }
  var a = t.closest('[data-act]'); if (!a) return;
  var act = a.getAttribute('data-act');
  if (ev.type === 'keydown' && ev.key !== 'Enter' && ev.key !== ' ') return;
  if (ev.type === 'keydown') ev.preventDefault();
  if (act === 'room') { var r = findRoom(a.getAttribute('data-id')); nav(r.id, r.secs[0].id); }
  else if (act === 'sec') nav(ST.room, a.getAttribute('data-id'));
  else if (act === 'leaf') { var go2 = a.getAttribute('data-go').split('.'); ST.leaf = a.getAttribute('data-key'); ST.menuOpen = false; nav(go2[0], go2[1]); }
  else if (act === 'fold') { var fk = a.getAttribute('data-key'); ST.open[fk] = a.getAttribute('aria-expanded') !== 'true'; render(); var nb = document.querySelectorAll('[data-act=fold]'); Array.prototype.forEach.call(nb, function (x) { if (x.getAttribute('data-key') === fk) x.focus(); }); }
  else if (act === 'menu') { ST.menuOpen = !ST.menuOpen; render(); }
  else if (act === 'tab') { ST.tab = a.getAttribute('data-tab'); ST.step = 0; ST.drawer = null; render(); }
  else if (act === 'toggleCols') { ST.showAll = !ST.showAll; render(); }
  else if (act === 'step') { ST.step = +a.getAttribute('data-n'); render(); window.scrollTo && document.getElementById('main') && document.getElementById('main').scrollIntoView && 0; }
  else if (act === 'toast') toast(a.getAttribute('data-msg') || 'Done');
  else if (act === 'openAction') { var n = +a.getAttribute('data-n'); ST.scr.openAction = n < 0 ? null : n; render(); }
  else if (act === 'closeDrawer') { ST.drawer = null; var d = document.getElementById('drawerwrap'); if (d) d.remove(); }
  else if (act === 'editRow') { ST.drawer = null; ST.tab = 'edit'; render(); }
  else if (act === 'confirmDelete') toast('Deleted (design preview)');
  else if (act === 'palette') palette();
  else if (act === 'noop') { /* design preview */ }
  else if (act === 'go') { var g = a.getAttribute('data-go').split('.'); ST.leaf = null; ST.menuOpen = false; nav(g[0], g[1], g[2]); }
  else if (act === 'dueToggle') { var C = ST.scr.counter; C.items[+a.getAttribute('data-n')] = a.checked; render(); }
  else if (act === 'stu') { ST.scr.counter.stu = +a.getAttribute('data-n'); render(); }
  else if (act === 'method') { ST.scr.counter.method = a.getAttribute('data-m'); render(); }
  else if (act === 'brush') { ST.scr.att.brush = a.getAttribute('data-s'); render(); }
  else if (act === 'seat') { var A = ST.scr.att, i = +a.getAttribute('data-n'); A.st[i] = A.st[i] === A.brush ? undefined : A.brush; render(); }
  else if (act === 'markAll') { var A2 = ST.scr.att; for (var q = 0; q < 30; q++) if (!A2.st[q]) A2.st[q] = A2.brush; render(); }
  else if (act === 'qpick') { ST.scr.marks.cur = +a.getAttribute('data-n'); render(); }
  else if (act === 'markAbsent') { var M = ST.scr.marks; M.v[M.cur] = 'AB'; M.cur = Math.min(M.cur + 1, 7); render(); }
  else if (act === 'markNext') { var M2 = ST.scr.marks; M2.cur = Math.min(M2.cur + 1, 7); ST.focusMark = true; render(); }
  else if (act === 'perm') { var P = ST.scr.perm, k = a.getAttribute('data-k'); P[k] = !a.classList.contains('y'); render(); }
}
function init() {
  APP = document.getElementById('app'); MAIN = APP;
  document.getElementById('css-spectrum').disabled = true;
  document.addEventListener('click', delegate);
  document.addEventListener('keydown', function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && ev.key.toLowerCase() === 'k') { ev.preventDefault(); if (!document.getElementById('pal')) palette(); return; }
    if (ev.target && ev.target.closest && ev.target.closest('[data-act],[data-sw],[data-pick]') && (ev.key === 'Enter' || ev.key === ' ')) delegate(ev);
  });
  document.addEventListener('input', function (ev) {
    var t = ev.target;
    if (t.id === 'q') { ST.q = t.value; ST.focusQ = true; render(); }
    else if (t.id === 'markinput') { var M = ST.scr.marks; M.v[M.cur] = t.value.toUpperCase() === 'A' ? 'AB' : t.value; ST.focusMark = true; render(); }
  });
  document.getElementById('tools').addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-tool]'); if (!b) return; var k = b.getAttribute('data-tool');
    if (k === 'web' || k === 'phone') { ST.device = k; layout(); } else if (k === 'clay' || k === 'spectrum') setTheme(k); else if (k === 'keys') ST.keys = !ST.keys;
    tools(); layout(); render();
  });
  var h = (location.hash || '').replace('#', '').split('.');
  if (h.length === 2) { var r = ROOMS.filter(function (x) { return x.id === h[0]; })[0]; if (r && r.secs.some(function (s) { return s.id === h[1]; })) { ST.room = h[0]; ST.sec = h[1]; } }
  window.addEventListener('resize', function () { layout(); });
  tools(); layout(); render();
}
init();
})();
