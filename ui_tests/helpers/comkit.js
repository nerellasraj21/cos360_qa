async function findTemplate(api, name) {
  const res = await api('GET', '/communication/templates');
  const rows = Array.isArray(res.data) ? res.data : [];
  return rows.find((t) => t.name === name);
}

async function createTemplate(api, cleanup, { name, channel = 'sms', body, subject }) {
  const res = await api('POST', '/communication/templates', { body: { name, channel, body, subject } });
  if (res.status !== 201) throw new Error(`template create failed ${res.status} ${JSON.stringify(res.data)}`);
  cleanup(() => api('DELETE', `/communication/templates/${res.data.id}`));
  return res.data;
}

module.exports = { findTemplate, createTemplate };

async function ensureStaffRecruiting(api) {
  const body = 'Dear {{name}}, welcome to the team.';
  const found = await findTemplate(api, 'Staff Recruiting');
  if (!found) {
    const res = await api('POST', '/communication/templates', { body: { name: 'Staff Recruiting', channel: 'sms', body } });
    if (res.status === 201) return res.data;
    return findTemplate(api, 'Staff Recruiting');
  }
  if (found.body !== body || !found.is_active) {
    await api('PUT', `/communication/templates/${found.id}`, { body: { body, is_active: true } });
  }
  return found;
}

module.exports.ensureStaffRecruiting = ensureStaffRecruiting;
