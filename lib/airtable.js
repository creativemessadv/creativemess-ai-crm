// Airtable lato server (per gli agenti). Il CRM nel browser continua a usare il proprio token.
// Scriviamo solo campi che il CRM gia usa, con typecast per le opzioni dei menu a tendina.

const configured = () => !!process.env.AIRTABLE_TOKEN;
const baseId = () => process.env.AIRTABLE_BASE_ID || 'appCyLdd90EgNzTv5';

async function call(method, path, body) {
  const r = await fetch(`https://api.airtable.com/v0/${baseId()}/${path}`, {
    method,
    headers: { Authorization: `Bearer ${process.env.AIRTABLE_TOKEN}`, 'content-type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const d = await r.json();
  if (!r.ok) throw new Error('Airtable: ' + ((d.error && (d.error.message || d.error.type)) || r.status));
  return d;
}

async function create(table, fields) {
  return call('POST', encodeURIComponent(table), { fields, typecast: true });
}

async function update(table, id, fields) {
  return call('PATCH', `${encodeURIComponent(table)}/${id}`, { fields, typecast: true });
}

module.exports = { configured, create, update };
