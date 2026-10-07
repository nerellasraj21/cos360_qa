function list(res) {
  return Array.isArray(res.data) ? res.data : (res.data && (res.data.items || res.data.data)) || [];
}

async function typeByName(api, name) {
  const res = await api('GET', '/expense/types/?limit=1000');
  return list(res).find((t) => t.name === name);
}

async function createTransaction(api, fields = {}) {
  const tag = Date.now().toString(36) + Math.floor(Math.random() * 1000);
  const type = await typeByName(api, fields.typeName || 'Electricity Bill');
  const res = await api('POST', '/expense/transactions/', {
    body: {
      expense_type_id: type.id,
      amount: String(fields.amount || '500.00'),
      transaction_date: fields.date || new Date().toISOString().slice(0, 10),
      description: fields.description || `QA txn ${tag}`,
      payment_method: fields.payment_method || 'cash',
      vendor_name: fields.vendor_name || `QA Vendor ${tag}`,
      idempotency_key: `qa-ui-${tag}`,
    },
  });
  if (res.status !== 201) throw new Error(`transaction create failed ${res.status} ${JSON.stringify(res.data)}`);
  return res.data;
}

async function findTransaction(api, vendor) {
  const res = await api('GET', '/expense/transactions/?limit=1000');
  return list(res).find((t) => t.vendor_name === vendor);
}

async function findByName(api, path, name) {
  const res = await api('GET', `${path}?limit=1000`);
  return list(res).find((r) => r.name === name);
}

function inr(value) {
  return Number(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

module.exports = { list, typeByName, createTransaction, findTransaction, findByName, inr };
