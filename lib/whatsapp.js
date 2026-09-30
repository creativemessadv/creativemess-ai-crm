// WhatsApp Cloud API (Meta): lettura dei webhook, verifica firma, invio messaggi.

const crypto = require('crypto');

const GRAPH = () => `https://graph.facebook.com/${process.env.META_GRAPH_VERSION || 'v23.0'}`;
const configured = () => !!(process.env.WHATSAPP_TOKEN && process.env.WHATSAPP_PHONE_NUMBER_ID);

// Legge il corpo grezzo della richiesta (serve per verificare la firma HMAC di Meta).
// Va chiamato PRIMA di toccare req.body, che altrimenti consuma lo stream.
function readRawBody(req) {
  if (req.readableEnded) return Promise.resolve(null);
  return new Promise((ok) => {
    const chunks = [];
    const timer = setTimeout(() => ok(chunks.length ? Buffer.concat(chunks).toString('utf8') : null), 5000);
    req.on('data', (c) => chunks.push(Buffer.isBuffer(c) ? c : Buffer.from(c)));
    req.on('end', () => { clearTimeout(timer); ok(Buffer.concat(chunks).toString('utf8')); });
    req.on('error', () => { clearTimeout(timer); ok(null); });
  });
}

function validSignature(raw, header) {
  const secret = process.env.META_APP_SECRET;
  if (!secret) return true; // verifica disattivata (sconsigliato in produzione)
  if (!raw || !header || !header.startsWith('sha256=')) return false;
  const expected = 'sha256=' + crypto.createHmac('sha256', secret).update(raw, 'utf8').digest('hex');
  const a = Buffer.from(expected);
  const b = Buffer.from(header);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

// Estrae i messaggi in arrivo dal payload del webhook.
// Ritorna [{id, from, name, ts, type, text, referral}] — referral e presente se il cliente arriva da un annuncio.
function parseIncoming(body) {
  const out = [];
  for (const entry of (body && body.entry) || []) {
    for (const change of entry.changes || []) {
      const v = change.value || {};
      const names = {};
      for (const c of v.contacts || []) names[c.wa_id] = (c.profile && c.profile.name) || '';
      for (const m of v.messages || []) {
        let text = '';
        if (m.type === 'text') text = (m.text && m.text.body) || '';
        else if (m.type === 'button') text = (m.button && m.button.text) || '';
        else if (m.type === 'interactive') {
          const i = m.interactive || {};
          text = (i.button_reply && i.button_reply.title) || (i.list_reply && i.list_reply.title) || '';
        } else text = `[${m.type} — contenuto non testuale]`;
        out.push({
          id: m.id,
          from: m.from,
          name: names[m.from] || '',
          ts: Number(m.timestamp || 0) * 1000 || Date.now(),
          type: m.type,
          text,
          referral: m.referral
            ? {
                adId: m.referral.source_id || '',
                sourceType: m.referral.source_type || '',
                headline: m.referral.headline || '',
                body: m.referral.body || '',
                url: m.referral.source_url || '',
                ctwaClid: m.referral.ctwa_clid || '',
              }
            : null,
        });
      }
    }
  }
  return out;
}

async function send(payload) {
  const r = await fetch(`${GRAPH()}/${process.env.WHATSAPP_PHONE_NUMBER_ID}/messages`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${process.env.WHATSAPP_TOKEN}`, 'content-type': 'application/json' },
    body: JSON.stringify(Object.assign({ messaging_product: 'whatsapp' }, payload)),
  });
  const d = await r.json();
  if (!r.ok) throw new Error('WhatsApp: ' + ((d.error && d.error.message) || r.status));
  return d;
}

// WhatsApp accetta max 4096 caratteri per messaggio di testo
async function sendText(to, text) {
  const chunks = [];
  let t = String(text);
  while (t.length > 3900) {
    let cut = t.lastIndexOf('\n', 3900);
    if (cut < 500) cut = 3900;
    chunks.push(t.slice(0, cut));
    t = t.slice(cut);
  }
  chunks.push(t);
  for (const c of chunks) await send({ to, type: 'text', text: { body: c, preview_url: false } });
}

// Segna come letto (spunte blu) — non bloccante
function markRead(messageId) {
  return send({ status: 'read', message_id: messageId }).catch(() => null);
}

module.exports = { configured, readRawBody, validSignature, parseIncoming, sendText, markRead };
