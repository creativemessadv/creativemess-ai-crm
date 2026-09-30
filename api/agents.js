// API della Macchina Lead per il CRM (sezione "📲 Macchina Lead") + cron giornaliero.
//
// Autenticazione: header x-crm-key = CRM_API_KEY (inseriscila nel CRM in ⚙️ Configurazione).
// Cron Vercel:    GET /api/agents?run=daily con Authorization: Bearer CRON_SECRET.
//
// GET  ?view=overview              agenti, configurazione, conversazioni, proposte, ultimo report
// GET  ?view=conv&phone=39...      conversazione completa
// POST {action:'analista'}                                  esegue l'Analista
// POST {action:'mediabuyer'}                                esegue il Media buyer sull'ultimo report
// POST {action:'creativo', offer, target, notes, count}     genera varianti di annunci
// POST {action:'decide', id, decision:'approve'|'reject'}   approva/rifiuta una proposta
// POST {action:'send', phone, text}                         Roberto scrive al cliente su WhatsApp
// POST {action:'status', phone, status:'bot'|'human'}       ridai la chat al bot / prendila tu

const crypto = require('crypto');
const kv = require('../lib/kv');
const wa = require('../lib/whatsapp');
const meta = require('../lib/meta-ads');
const airtable = require('../lib/airtable');
const agents = require('../lib/lead-agents');

function safeEqual(a, b) {
  const x = Buffer.from(String(a || ''));
  const y = Buffer.from(String(b || ''));
  return x.length > 0 && x.length === y.length && crypto.timingSafeEqual(x, y);
}

function summary(c) {
  const last = c.messages[c.messages.length - 1] || {};
  return {
    phone: c.phone,
    name: (c.profile && (c.profile.nome || c.profile.azienda)) || c.name || '',
    status: c.status,
    stage: c.stage,
    score: c.score,
    servizio: (c.profile && c.profile.servizio) || '',
    sintesi: (c.profile && c.profile.sintesi) || '',
    adId: (c.referral && c.referral.adId) || '',
    adHeadline: (c.referral && c.referral.headline) || '',
    lastText: (last.text || '').slice(0, 140),
    lastRole: last.role || '',
    updatedAt: c.updatedAt,
    createdAt: c.createdAt,
  };
}

module.exports = async (req, res) => {
  const q = req.query || {};

  // Cron giornaliero
  if (req.method === 'GET' && q.run === 'daily') {
    const secret = process.env.CRON_SECRET;
    const auth = req.headers.authorization || '';
    if (!secret || !safeEqual(auth, `Bearer ${secret}`)) return res.status(401).json({ error: 'Non autorizzato' });
    try {
      const out = await agents.dailyRun();
      return res.json({ ok: true, totals: out.report.totals, proposals: out.mediaBuyer.proposals.length });
    } catch (e) {
      return res.status(500).json({ error: e.message });
    }
  }

  if (!process.env.CRM_API_KEY) {
    return res.status(503).json({ error: 'CRM_API_KEY non configurata su Vercel (Settings > Environment Variables), poi Redeploy.' });
  }
  if (!safeEqual(req.headers['x-crm-key'], process.env.CRM_API_KEY)) {
    return res.status(401).json({ error: 'Chiave API agenti non valida: inseriscila in ⚙️ Configurazione.' });
  }

  try {
    if (req.method === 'GET') {
      if (q.view === 'conv') {
        const conv = await agents.getConv(String(q.phone || ''));
        if (!conv) return res.status(404).json({ error: 'Conversazione non trovata' });
        return res.json({ conv });
      }
      const [convs, proposals, report] = await Promise.all([
        agents.listConvs(200),
        agents.listProposals(),
        kv.get(agents.REPORT_KEY),
      ]);
      return res.json({
        agents: agents.AGENTS_INFO,
        config: {
          ai: !!process.env.ANTHROPIC_API_KEY,
          redis: kv.hasRedis(),
          whatsapp: wa.configured(),
          metaAds: meta.configured(),
          metaWrite: meta.writeEnabled(),
          airtable: airtable.configured(),
          telegram: !!process.env.TELEGRAM_BOT_TOKEN,
        },
        convs: convs.map(summary),
        proposals: proposals.slice(0, 50),
        report,
      });
    }

    if (req.method !== 'POST') return res.status(405).json({ error: 'Metodo non consentito' });
    const b = req.body || {};
    switch (b.action) {
      case 'analista':
        return res.json({ report: await agents.analista() });
      case 'mediabuyer':
        return res.json(await agents.mediaBuyer());
      case 'creativo':
        return res.json({ proposal: await agents.creativo(b) });
      case 'decide':
        return res.json({ proposal: await agents.decideProposal(b.id, b.decision === 'approve' ? 'approve' : 'reject') });
      case 'send':
        if (!b.phone || !String(b.text || '').trim()) return res.status(400).json({ error: 'Servono telefono e testo' });
        return res.json({ conv: await agents.sendHumanMessage(String(b.phone), String(b.text).trim()) });
      case 'status':
        return res.json({ conv: await agents.setConvStatus(String(b.phone || ''), b.status) });
      default:
        return res.status(400).json({ error: 'Azione sconosciuta' });
    }
  } catch (e) {
    return res.status(500).json({ error: e.message });
  }
};

module.exports.config = { maxDuration: 60 };
