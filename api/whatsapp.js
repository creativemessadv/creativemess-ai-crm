// Webhook WhatsApp Cloud API — ingresso della Macchina Lead.
//
// Setup (una volta sola): vedi MACCHINA-LEAD.md
//   Meta for Developers → WhatsApp → Configurazione → Webhook
//     URL:               https://<dominio>/api/whatsapp
//     Token di verifica:  valore di WHATSAPP_VERIFY_TOKEN
//     Campi:             messages
//
// Stato: https://<dominio>/api/whatsapp  (mostra cosa e configurato)

const wa = require('../lib/whatsapp');
const kv = require('../lib/kv');
const { handleIncoming } = require('../lib/lead-agents');

module.exports = async (req, res) => {
  const q = req.query || {};

  if (req.method === 'GET') {
    // Verifica del webhook da parte di Meta
    if (q['hub.mode'] === 'subscribe') {
      const expected = process.env.WHATSAPP_VERIFY_TOKEN;
      if (expected && q['hub.verify_token'] === expected) {
        res.setHeader('content-type', 'text/plain');
        return res.status(200).send(String(q['hub.challenge'] || ''));
      }
      return res.status(403).send('Token di verifica non valido');
    }
    return res.json({
      ok: true,
      servizio: 'Macchina Lead — webhook WhatsApp',
      whatsapp: wa.configured() ? 'configurato' : 'MANCANO WHATSAPP_TOKEN e/o WHATSAPP_PHONE_NUMBER_ID',
      verifica_webhook: process.env.WHATSAPP_VERIFY_TOKEN ? 'ok' : 'MANCA WHATSAPP_VERIFY_TOKEN',
      firma: process.env.META_APP_SECRET ? 'verificata (META_APP_SECRET)' : 'NON verificata — consigliato META_APP_SECRET',
      ai: process.env.ANTHROPIC_API_KEY ? 'ok' : 'MANCA ANTHROPIC_API_KEY',
      memoria: kv.hasRedis() ? 'Redis (permanente)' : 'temporanea — configura Upstash',
    });
  }

  if (req.method !== 'POST') return res.status(405).end();

  const raw = await wa.readRawBody(req);
  if (!wa.validSignature(raw, req.headers['x-hub-signature-256'])) {
    return res.status(401).send('Firma non valida');
  }

  let body;
  try {
    body = raw ? JSON.parse(raw) : req.body;
  } catch (e) {
    return res.status(400).send('JSON non valido');
  }

  // Rispondiamo 200 in ogni caso: i duplicati sono filtrati e un errore su un messaggio
  // non deve far ripetere a Meta l'intero pacchetto all'infinito.
  const results = [];
  if (wa.configured()) {
    for (const msg of wa.parseIncoming(body)) {
      try {
        results.push(await handleIncoming(msg));
      } catch (e) {
        console.error('Macchina Lead — errore su messaggio', msg.id, e.message);
        results.push({ error: e.message });
      }
    }
  }
  return res.status(200).json({ ok: true, results });
};

module.exports.config = { maxDuration: 60 };
