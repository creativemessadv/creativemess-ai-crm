// Macchina Lead — i 5 agenti del circuito Meta Ads → WhatsApp → CRM.
//
//   💬 Venditore WhatsApp  risponde ai contatti in arrivo dagli annunci Click-to-WhatsApp
//   🎯 Qualificatore       aggiorna la scheda del lead dopo ogni scambio
//   📊 Analista            costo per lead QUALIFICATO per annuncio (Meta + CRM)
//   📢 Media buyer         propone budget/pause (serve approvazione)
//   🎨 Creativo            propone varianti di annuncio (serve approvazione)
//
// Vedi MACCHINA-LEAD.md per il piano completo.

const kv = require('./kv');
const { ask, askStruct } = require('./claude');
const wa = require('./whatsapp');
const meta = require('./meta-ads');
const airtable = require('./airtable');

const MAX_STORED = 60; // messaggi conservati per conversazione
const MAX_CONTEXT = 30; // messaggi inviati al modello
const HOT_SCORE = 70;
const DAY = 24 * 3600 * 1000;

const CONV_KEY = (phone) => `wa:conv:${phone}`;
const INDEX_KEY = 'wa:index';
const PROPOSALS_KEY = 'lead:proposals';
const REPORT_KEY = 'lead:report:last';

const AGENTS_INFO = [
  { id: 'venditore', icon: '💬', name: 'Venditore WhatsApp', spec: 'Risponde in pochi secondi ai contatti dagli annunci, qualifica con domande naturali, propone la call' },
  { id: 'qualificatore', icon: '🎯', name: 'Qualificatore', spec: 'Scheda lead: bisogno, budget, tempi, decisore, punteggio 0-100 e stadio' },
  { id: 'analista', icon: '📊', name: 'Analista', spec: 'Costo per lead e per lead qualificato di ogni annuncio, vincenti e perdenti' },
  { id: 'mediabuyer', icon: '📢', name: 'Media buyer', spec: 'Propone aumenti, riduzioni e pause di budget — esegue solo dopo approvazione' },
  { id: 'creativo', icon: '🎨', name: 'Creativo', spec: 'Varianti di annunci Click-to-WhatsApp: testo, titolo, messaggio iniziale, concept immagine' },
];

const AZIENDA = `Creative Mess ADV — web agency italiana 100% AI-powered, sede a Milano, titolare Roberto Salvatori.
Clienti: PMI italiane, professionisti, partite IVA.
Listino indicativo (mai sconti o garanzie di risultato):
- sito vetrina €1.500-4.000 · e-commerce €3.000-12.000 · landing page da €800
- SEO €500-2.000/mese · Google Ads (gestione) €400-1.500/mese · Meta Ads (gestione) €400-1.200/mese
- social media €500-1.500/mese · email marketing e automazioni su preventivo
Il budget pubblicitario (quanto si paga a Google/Meta) e separato dalla gestione.`;

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

// ── Conversazioni ─────────────────────────────────────────────────────────────

function newConv(phone, name) {
  return {
    phone,
    name: name || '',
    createdAt: Date.now(),
    updatedAt: Date.now(),
    lastUserTs: 0,
    status: 'bot', // bot | human | stop
    referral: null, // annuncio di provenienza
    messages: [], // [{role:'user'|'assistant'|'human', text, ts}]
    profile: {},
    score: 0,
    stage: 'nuovo',
    hotNotified: false,
    airtableId: null,
  };
}

async function getConv(phone) {
  return kv.get(CONV_KEY(phone));
}

async function saveConv(conv) {
  conv.updatedAt = Date.now();
  conv.messages = conv.messages.slice(-MAX_STORED);
  await kv.set(CONV_KEY(conv.phone), conv);
  await kv.zadd(INDEX_KEY, conv.updatedAt, conv.phone);
}

async function listConvs(limit = 100) {
  const phones = await kv.zrevrange(INDEX_KEY, 0, limit - 1);
  const convs = await kv.mget(phones.map(CONV_KEY));
  return convs.filter(Boolean);
}

// Lock per conversazione: due messaggi ravvicinati non devono sovrascriversi a vicenda.
async function withLock(phone, fn) {
  const key = `wa:lock:${phone}`;
  for (let i = 0; i < 20; i++) {
    if (await kv.setOnce(key, 45)) {
      try { return await fn(); } finally { await kv.del(key); }
    }
    await sleep(1500);
  }
  return fn(); // lock scaduto male: meglio rispondere che perdere il messaggio
}

// La conversazione come testo per gli agenti
function transcript(conv, n = MAX_CONTEXT) {
  const who = { user: 'CLIENTE', assistant: 'ASSISTENTE', human: 'ROBERTO (umano)' };
  return conv.messages.slice(-n).map((m) => `${who[m.role] || m.role}: ${m.text}`).join('\n');
}

function referralText(conv) {
  const r = conv.referral;
  if (!r) return 'Contatto diretto (non da annuncio).';
  return `Arriva dall'annuncio ${r.adId || 'n/d'} — titolo: "${r.headline || ''}" — testo: "${(r.body || '').slice(0, 300)}"`;
}

// ── 💬 Venditore WhatsApp ─────────────────────────────────────────────────────

const VENDITORE_SYSTEM = `Sei l'assistente digitale di Creative Mess ADV su WhatsApp.
${AZIENDA}

IL TUO LAVORO
Rispondi ai contatti arrivati dagli annunci su Facebook/Instagram. Obiettivo: capire il bisogno,
qualificare il contatto e, se e in target, fissare una call conoscitiva gratuita di 20 minuti con Roberto.

COME SCRIVI
- Italiano, tono cordiale e professionale, come un bravo commerciale su WhatsApp. Dai del lei
  a meno che il cliente non dia del tu.
- Messaggi BREVI: massimo 3 frasi, una sola domanda per messaggio. Niente elenchi lunghi, niente markdown,
  al massimo un'emoji.
- Nel PRIMO messaggio della conversazione presentati come assistente digitale di Creative Mess ADV
  e ringrazia per il contatto; se il cliente arriva da un annuncio, aggancia il tema dell'annuncio.
- Chiedi in modo naturale cio che manca nella SCHEDA LEAD: servizio che serve, attivita e citta,
  sito attuale, budget indicativo, tempi, se e lui a decidere. Non fare interrogatori: una cosa alla volta.
- Prezzi: puoi dare solo le fasce del listino, spiegando che il preventivo preciso arriva dopo la call.
- Quando il lead e qualificato (bisogno chiaro + budget compatibile + tempi entro 3 mesi) proponi la call:
  chiedi giorno e fascia oraria preferiti e di' che Roberto confermera a breve. Non inventare disponibilita.
- Se non e in target (budget troppo basso, cerca lavoro, spam) chiudi con gentilezza.

REGOLE FERME
- Mai promettere risultati, posizionamenti, numeri di clienti o sconti.
- Mai inventare casi studio o clienti.
- Se il cliente chiede di parlare con una persona, e arrabbiato, pone domande legali/contrattuali
  o chiede qualcosa che non sai: rispondi che lo fai richiamare da Roberto e imposta handoff=true.
- Se chiede come vengono trattati i dati, rimanda all'informativa privacy{{PRIVACY}}.`;

async function venditore(conv) {
  const privacy = process.env.PRIVACY_URL ? ` (${process.env.PRIVACY_URL})` : '';
  const system = VENDITORE_SYSTEM.replace('{{PRIVACY}}', privacy);
  const firstReply = !conv.messages.some((m) => m.role === 'assistant' || m.role === 'human');
  const content = `PROVENIENZA: ${referralText(conv)}
NOME PROFILO WHATSAPP: ${conv.name || 'n/d'}
SCHEDA LEAD ATTUALE: ${JSON.stringify(conv.profile || {})} — punteggio ${conv.score}/100, stadio ${conv.stage}
${firstReply ? 'E il tuo PRIMO messaggio in questa conversazione.' : ''}

CONVERSAZIONE:
${transcript(conv)}

Scrivi la prossima risposta dell'ASSISTENTE.`;

  return askStruct({
    system,
    messages: [{ role: 'user', content }],
    name: 'rispondi_su_whatsapp',
    description: 'Invia la risposta al cliente su WhatsApp.',
    schema: {
      type: 'object',
      properties: {
        reply: { type: 'string', description: 'Il messaggio da inviare, testo semplice, massimo 3 frasi.' },
        handoff: { type: 'boolean', description: 'true se la conversazione deve passare a Roberto (umano).' },
        handoffReason: { type: 'string', description: 'Motivo del passaggio a umano, se handoff=true.' },
      },
      required: ['reply', 'handoff'],
    },
    maxTokens: 800,
  });
}

// ── 🎯 Qualificatore ──────────────────────────────────────────────────────────

const QUALIFICATORE_SYSTEM = `Sei il Qualificatore di Creative Mess ADV. Leggi una conversazione WhatsApp
tra un potenziale cliente e l'assistente e aggiorni la scheda del lead. Riporti solo cio che il cliente
ha detto o che e chiaramente deducibile: se un dato non c'e, lascialo vuoto. Non inventare.
${AZIENDA}

PUNTEGGIO 0-100
- Bisogno chiaro e tra i nostri servizi: fino a 30
- Budget dichiarato compatibile con il listino: fino a 25
- Tempi: entro 30 giorni 20, 1-3 mesi 12, oltre 3 mesi o vago 3
- Parla con il decisore (titolare/socio/responsabile marketing): fino a 15
- Fit: PMI/professionista italiano con attivita reale: fino a 10
STADI
- nuovo: nessuna informazione utile ancora
- in_qualifica: conversazione in corso, dati parziali
- caldo: punteggio >= ${HOT_SCORE} oppure ha chiesto/accettato la call
- tiepido: interessato ma budget o tempi deboli
- freddo: ha smesso di rispondere con interesse o rimanda senza data
- non_target: fuori target (cerca lavoro, spam, budget incompatibile, fornitore)`;

async function qualificatore(conv) {
  return askStruct({
    system: QUALIFICATORE_SYSTEM,
    messages: [{
      role: 'user',
      content: `PROVENIENZA: ${referralText(conv)}\nSCHEDA PRECEDENTE: ${JSON.stringify(conv.profile || {})}\n\nCONVERSAZIONE:\n${transcript(conv)}`,
    }],
    name: 'aggiorna_scheda_lead',
    description: 'Salva la scheda aggiornata del lead nel CRM.',
    schema: {
      type: 'object',
      properties: {
        nome: { type: 'string' },
        azienda: { type: 'string' },
        settore: { type: 'string' },
        citta: { type: 'string' },
        email: { type: 'string' },
        sitoAttuale: { type: 'string' },
        servizio: { type: 'string', description: 'Servizio richiesto, es. "Sito vetrina", "Meta Ads", "SEO"' },
        budget: { type: 'string', description: 'Budget come dichiarato dal cliente' },
        valoreStimato: { type: 'number', description: 'Stima in euro del primo contratto, secondo il listino. 0 se ignoto.' },
        tempi: { type: 'string' },
        decisore: { type: 'string', enum: ['si', 'no', 'non_so'] },
        disponibilitaCall: { type: 'string', description: 'Giorno/orario proposto dal cliente per la call, se c\'e' },
        score: { type: 'integer', minimum: 0, maximum: 100 },
        stage: { type: 'string', enum: ['nuovo', 'in_qualifica', 'caldo', 'tiepido', 'freddo', 'non_target'] },
        sintesi: { type: 'string', description: 'Due righe per Roberto: chi e, cosa vuole, prossimo passo.' },
      },
      required: ['score', 'stage', 'sintesi'],
    },
    maxTokens: 1000,
    fast: true,
  });
}

// ── Notifiche a Roberto (bot Telegram esistente) ──────────────────────────────

async function notifyOwner(text) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) return;
  let chatId = process.env.TELEGRAM_OWNER_ID;
  if (!chatId) chatId = await kv.get('tg:owner').catch(() => null);
  if (!chatId) return;
  await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text: text.slice(0, 3900) }),
  }).catch(() => null);
}

function leadCard(conv) {
  const p = conv.profile || {};
  return [
    `${p.nome || conv.name || 'Contatto'}${p.azienda ? ' — ' + p.azienda : ''} (+${conv.phone})`,
    `Punteggio ${conv.score}/100 · ${conv.stage}`,
    p.servizio ? `Servizio: ${p.servizio}` : '',
    p.budget ? `Budget: ${p.budget}` : '',
    p.tempi ? `Tempi: ${p.tempi}` : '',
    p.disponibilitaCall ? `Disponibilita call: ${p.disponibilitaCall}` : '',
    p.sintesi ? `\n${p.sintesi}` : '',
    conv.referral && conv.referral.adId ? `\nAnnuncio: ${conv.referral.adId}` : '',
  ].filter(Boolean).join('\n');
}

// Lead caldo -> PIPELINE Airtable (una volta sola)
async function pushToPipeline(conv) {
  if (!airtable.configured() || conv.airtableId) return;
  const p = conv.profile || {};
  const r = await airtable.create('PIPELINE', {
    'Nome Deal': `${p.azienda || p.nome || conv.name || '+' + conv.phone} (WhatsApp)`,
    Servizio: p.servizio || '',
    'Valore Stimato': Number(p.valoreStimato) || 0,
    Fase: 'Lead',
  });
  conv.airtableId = r.id;
}

// ── Gestione di un messaggio in arrivo ────────────────────────────────────────

const STOP_RE = /^\s*(stop|basta|cancellami|non scrivermi( pi[uù])?|disiscrivimi|unsubscribe)\s*[.!]*\s*$/i;

async function handleIncoming(msg) {
  // Meta ripete il webhook se non risponde in tempo: ogni messaggio va gestito una volta sola
  if (!(await kv.setOnce(`wa:seen:${msg.id}`, 2 * 24 * 3600))) return { skipped: 'duplicato' };

  return withLock(msg.from, async () => {
    const conv = (await getConv(msg.from)) || newConv(msg.from, msg.name);
    if (msg.name && !conv.name) conv.name = msg.name;
    if (msg.referral && !conv.referral) conv.referral = msg.referral;
    conv.messages.push({ role: 'user', text: msg.text, ts: msg.ts });
    conv.lastUserTs = msg.ts;
    wa.markRead(msg.id);

    // Opt-out: si conferma una volta e poi silenzio
    if (STOP_RE.test(msg.text)) {
      if (conv.status !== 'stop') {
        conv.status = 'stop';
        const bye = 'Ricevuto, non la contatteremo piu. Se in futuro le serve una mano, ci scriva pure qui.';
        await wa.sendText(conv.phone, bye);
        conv.messages.push({ role: 'assistant', text: bye, ts: Date.now() });
      }
      await saveConv(conv);
      return { status: 'stop' };
    }

    // Chat in mano a Roberto (o cliente che aveva chiesto STOP e ora riscrive): il bot tace
    if (conv.status === 'stop') conv.status = 'human';
    if (conv.status === 'human') {
      await saveConv(conv);
      await notifyOwner(`💬 Nuovo messaggio WhatsApp (chat gestita da te)\n${conv.name || '+' + conv.phone}: ${msg.text}`);
      return { status: 'human' };
    }

    // 💬 Venditore
    const out = await venditore(conv);
    const reply = String(out.reply || '').trim();
    if (reply) {
      await wa.sendText(conv.phone, reply);
      conv.messages.push({ role: 'assistant', text: reply, ts: Date.now() });
    }
    if (out.handoff) {
      conv.status = 'human';
      conv.handoffReason = out.handoffReason || '';
    }

    // 🎯 Qualificatore (se fallisce, la risposta al cliente e comunque partita)
    try {
      const q = await qualificatore(conv);
      const { score, stage, ...profile } = q;
      conv.profile = Object.assign({}, conv.profile, profile);
      conv.score = score;
      conv.stage = stage;
    } catch (e) {
      conv.lastError = 'Qualificatore: ' + e.message;
    }

    if ((conv.stage === 'caldo' || conv.score >= HOT_SCORE) && !conv.hotNotified) {
      conv.hotNotified = true;
      try { await pushToPipeline(conv); } catch (e) { conv.lastError = e.message; }
      await notifyOwner(`🔥 LEAD CALDO da WhatsApp\n\n${leadCard(conv)}\n\nApri il CRM → Macchina Lead per rispondere.`);
    }
    if (out.handoff) {
      await notifyOwner(`🙋 Il cliente va gestito da te (${conv.handoffReason || 'richiesta'})\n\n${leadCard(conv)}`);
    }

    await saveConv(conv);
    return { status: conv.status, stage: conv.stage, score: conv.score };
  });
}

// Roberto scrive dal CRM (la chat passa in modalita umana)
async function sendHumanMessage(phone, text) {
  return withLock(phone, async () => {
    const conv = await getConv(phone);
    if (!conv) throw new Error('Conversazione non trovata');
    if (Date.now() - (conv.lastUserTs || 0) > DAY) {
      throw new Error('Sono passate piu di 24 ore dall\'ultimo messaggio del cliente: WhatsApp consente solo messaggi template. Contattalo per telefono.');
    }
    await wa.sendText(phone, text);
    conv.messages.push({ role: 'human', text, ts: Date.now() });
    conv.status = 'human';
    await saveConv(conv);
    return conv;
  });
}

async function setConvStatus(phone, status) {
  if (!['bot', 'human'].includes(status)) throw new Error('Stato non valido');
  return withLock(phone, async () => {
    const conv = await getConv(phone);
    if (!conv) throw new Error('Conversazione non trovata');
    conv.status = status;
    await saveConv(conv);
    return conv;
  });
}

// ── 📊 Analista ───────────────────────────────────────────────────────────────

const QUALIFIED = new Set(['caldo', 'tiepido']);
const round2 = (n) => Math.round(n * 100) / 100;

async function analista() {
  const since = Date.now() - 7 * DAY;
  const convs = (await listConvs(500)).filter((c) => c.createdAt >= since);

  // Lead del CRM raggruppati per annuncio di provenienza
  const byAd = {};
  for (const c of convs) {
    const adId = (c.referral && c.referral.adId) || 'diretto';
    const g = byAd[adId] || (byAd[adId] = { leads: 0, qualified: 0, hot: 0, nonTarget: 0, scoreSum: 0, headline: '' });
    g.leads++;
    g.scoreSum += c.score || 0;
    if (QUALIFIED.has(c.stage)) g.qualified++;
    if (c.stage === 'caldo') g.hot++;
    if (c.stage === 'non_target') g.nonTarget++;
    if (!g.headline && c.referral) g.headline = c.referral.headline || '';
  }

  let ads = [];
  let source = 'crm';
  let metaError = null;
  if (meta.configured()) {
    try {
      ads = await meta.adInsights('last_7d');
      source = 'meta+crm';
    } catch (e) {
      metaError = e.message;
    }
  }

  const rows = ads.map((a) => {
    const g = byAd[a.adId] || { leads: 0, qualified: 0, hot: 0, nonTarget: 0, scoreSum: 0 };
    delete byAd[a.adId];
    return {
      adId: a.adId, adName: a.adName, adsetId: a.adsetId, adsetName: a.adsetName, campaign: a.campaign,
      spend: round2(a.spend), impressions: a.impressions, ctr: round2(a.ctr), frequency: round2(a.frequency),
      metaConversations: a.conversations,
      leads: g.leads, qualified: g.qualified, hot: g.hot, nonTarget: g.nonTarget,
      avgScore: g.leads ? Math.round(g.scoreSum / g.leads) : 0,
      cpl: g.leads ? round2(a.spend / g.leads) : null,
      costPerQualified: g.qualified ? round2(a.spend / g.qualified) : null,
    };
  });
  // Annunci senza dati Meta (o contatti diretti)
  for (const [adId, g] of Object.entries(byAd)) {
    rows.push({
      adId, adName: g.headline || (adId === 'diretto' ? 'Contatti diretti' : adId), spend: null,
      leads: g.leads, qualified: g.qualified, hot: g.hot, nonTarget: g.nonTarget,
      avgScore: g.leads ? Math.round(g.scoreSum / g.leads) : 0, cpl: null, costPerQualified: null,
    });
  }

  const totals = rows.reduce((t, r) => {
    t.spend += r.spend || 0; t.leads += r.leads; t.qualified += r.qualified; t.hot += r.hot;
    return t;
  }, { spend: 0, leads: 0, qualified: 0, hot: 0 });
  totals.spend = round2(totals.spend);
  totals.cpl = totals.leads && totals.spend ? round2(totals.spend / totals.leads) : null;
  totals.costPerQualified = totals.qualified && totals.spend ? round2(totals.spend / totals.qualified) : null;

  let analysis = 'Nessun dato negli ultimi 7 giorni: servono annunci attivi o conversazioni WhatsApp.';
  if (rows.length) {
    analysis = await ask({
      system: `Sei l'Analista della Macchina Lead di Creative Mess ADV. Leggi le metriche degli ultimi 7 giorni
degli annunci Click-to-WhatsApp e dei lead generati. La metrica che conta e il COSTO PER LEAD QUALIFICATO
(stadi caldo/tiepido), non il costo per messaggio. Scrivi in italiano, massimo 250 parole, testo semplice:
1) situazione in 2 righe con i numeri totali; 2) annunci vincenti e perche; 3) annunci da tagliare e perche
(spesa senza lead qualificati, frequenza > 3 = pubblico saturo, molti non_target = messaggio sbagliato);
4) tre azioni concrete. Se i dati sono pochi (< 5 lead per annuncio) dillo e non trarre conclusioni forti.`,
      messages: [{ role: 'user', content: `TOTALI: ${JSON.stringify(totals)}\nPER ANNUNCIO: ${JSON.stringify(rows)}` }],
      maxTokens: 1200,
    });
  }

  const report = { ts: Date.now(), source, metaError, totals, rows, analysis };
  await kv.set(REPORT_KEY, report);
  return report;
}

// ── Proposte (Media buyer e Creativo) ─────────────────────────────────────────

async function listProposals() {
  return (await kv.get(PROPOSALS_KEY)) || [];
}

async function addProposals(items) {
  const all = await listProposals();
  const now = Date.now();
  const created = items.map((it, i) => Object.assign({ id: `p${now.toString(36)}${i}`, status: 'pending', createdAt: now }, it));
  await kv.set(PROPOSALS_KEY, created.concat(all).slice(0, 200));
  return created;
}

// ── 📢 Media buyer ────────────────────────────────────────────────────────────

async function mediaBuyer(report) {
  report = report || (await kv.get(REPORT_KEY));
  if (!report || !report.rows || !report.rows.some((r) => r.spend)) {
    return { proposals: [], note: 'Serve un report dell\'Analista con dati di spesa Meta.' };
  }
  let adsets = [];
  try { adsets = meta.configured() ? await meta.adsets() : []; } catch (e) { /* proposte senza budget attuale */ }

  const maxBudget = meta.maxDailyBudget();
  const out = await askStruct({
    system: `Sei il Media buyer della Macchina Lead di Creative Mess ADV. Budget piccoli, soldi contati.
Dal report dell'Analista proponi al massimo 5 azioni sugli adset/annunci Meta:
- budget: cambia il budget giornaliero di un ADSET (variazione massima ±30% per volta, tetto €${maxBudget}/giorno)
- pause: metti in pausa un ANNUNCIO che spende senza portare lead qualificati
Principi: premia il costo per lead qualificato piu basso, non il costo per messaggio; non decidere su meno
di €20 di spesa o meno di 3 lead; se i dati sono pochi, proponi meno azioni o nessuna.
Ogni azione deve avere un motivo con i numeri.`,
    messages: [{ role: 'user', content: `REPORT: ${JSON.stringify({ totals: report.totals, rows: report.rows })}\nADSET E BUDGET ATTUALI: ${JSON.stringify(adsets)}` }],
    name: 'proponi_azioni',
    description: 'Proponi azioni di media buying da far approvare a Roberto.',
    schema: {
      type: 'object',
      properties: {
        actions: {
          type: 'array',
          maxItems: 5,
          items: {
            type: 'object',
            properties: {
              action: { type: 'string', enum: ['budget', 'pause'] },
              objectId: { type: 'string', description: 'ID adset (per budget) o ID annuncio (per pause)' },
              objectName: { type: 'string' },
              toBudget: { type: 'number', description: 'Nuovo budget giornaliero in euro (solo per budget)' },
              reason: { type: 'string' },
            },
            required: ['action', 'objectId', 'reason'],
          },
        },
        note: { type: 'string', description: 'Commento generale in una riga' },
      },
      required: ['actions'],
    },
    maxTokens: 1500,
  });

  // Guardrail applicati in codice, non affidati al modello
  const budgets = Object.fromEntries(adsets.map((s) => [s.id, s.dailyBudget]));
  const items = [];
  for (const a of out.actions || []) {
    if (a.action === 'budget') {
      const from = budgets[a.objectId];
      if (!from || !(a.toBudget > 0)) continue;
      const to = round2(Math.min(maxBudget, Math.max(from * 0.7, Math.min(from * 1.3, a.toBudget))));
      if (to === from) continue;
      items.push({ type: 'media', action: 'budget', objectId: a.objectId, objectName: a.objectName || '', fromBudget: from, toBudget: to, reason: a.reason });
    } else if (a.action === 'pause') {
      items.push({ type: 'media', action: 'pause', objectId: a.objectId, objectName: a.objectName || '', reason: a.reason });
    }
  }
  const proposals = await addProposals(items);
  return { proposals, note: out.note || '' };
}

// ── 🎨 Creativo ───────────────────────────────────────────────────────────────

async function creativo({ offer, target, notes, count = 3 }) {
  if (!offer) throw new Error('Indica l\'offerta da promuovere');
  const report = await kv.get(REPORT_KEY);
  const winners = report && report.rows
    ? report.rows.filter((r) => r.qualified > 0).sort((a, b) => (a.costPerQualified || 1e9) - (b.costPerQualified || 1e9)).slice(0, 3)
    : [];

  const out = await askStruct({
    system: `Sei il Creativo della Macchina Lead di Creative Mess ADV. Scrivi annunci Meta (Facebook/Instagram)
con destinazione WhatsApp ("Click-to-WhatsApp") per PMI italiane.
${AZIENDA}
Regole:
- Hook nella prima riga, concreto, nella lingua del titolare di una PMI (clienti, telefono che squilla, tempo),
  non nel gergo da agenzia. Niente promesse di risultati garantiti, niente numeri inventati.
- Testo principale max 125 caratteri prima del "Altro", totale max 400. Titolo max 40 caratteri.
- Il messaggio precompilato e cio che il cliente invia con un tocco aprendo WhatsApp: breve e naturale
  (es. "Ciao, vorrei info sul sito per la mia attivita").
- Ogni variante usa un ANGOLO diverso (problema, risultato, obiezione, prezzo chiaro, urgenza reale...).
- Concept immagine descrivibile a un designer o a un generatore di immagini, formato 1:1 e 9:16.
- Rispetta le policy Meta: niente riferimenti a caratteristiche personali ("Sei un imprenditore in crisi?").`,
    messages: [{
      role: 'user',
      content: `OFFERTA: ${offer}\nTARGET: ${target || 'PMI e professionisti italiani'}\nNOTE: ${notes || '-'}
ANNUNCI CHE STANNO FUNZIONANDO: ${winners.length ? JSON.stringify(winners.map((w) => ({ nome: w.adName, costoPerQualificato: w.costPerQualified, qualificati: w.qualified }))) : 'nessun dato ancora'}
Scrivi ${Math.min(Math.max(count, 1), 5)} varianti.`,
    }],
    name: 'proponi_annunci',
    description: 'Proponi varianti di annunci Click-to-WhatsApp da far approvare.',
    schema: {
      type: 'object',
      properties: {
        variants: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              angle: { type: 'string' },
              primaryText: { type: 'string' },
              headline: { type: 'string' },
              description: { type: 'string' },
              prefilledMessage: { type: 'string' },
              imageConcept: { type: 'string' },
            },
            required: ['angle', 'primaryText', 'headline', 'prefilledMessage', 'imageConcept'],
          },
        },
      },
      required: ['variants'],
    },
    maxTokens: 3000,
  });

  const [proposal] = await addProposals([{ type: 'creative', offer, target: target || '', variants: out.variants || [] }]);
  return proposal;
}

// ── Approvazione ──────────────────────────────────────────────────────────────

async function decideProposal(id, decision) {
  const all = await listProposals();
  const p = all.find((x) => x.id === id);
  if (!p) throw new Error('Proposta non trovata');
  if (p.status !== 'pending') throw new Error('Proposta gia decisa');
  p.decidedAt = Date.now();

  if (decision === 'reject') {
    p.status = 'rejected';
  } else if (p.type === 'creative') {
    p.status = 'approved'; // la pubblicazione su Meta resta manuale in fase 1
  } else if (!meta.configured() || !meta.writeEnabled()) {
    p.status = 'approved_manual'; // da eseguire a mano in Gestione inserzioni
  } else {
    try {
      if (p.action === 'budget') await meta.setAdsetBudget(p.objectId, p.toBudget);
      else if (p.action === 'pause') await meta.setStatus(p.objectId, 'PAUSED');
      p.status = 'executed';
    } catch (e) {
      p.status = 'error';
      p.error = e.message;
    }
  }
  await kv.set(PROPOSALS_KEY, all);
  return p;
}

// ── Giro giornaliero (cron) ───────────────────────────────────────────────────

async function dailyRun() {
  const report = await analista();
  let mb = { proposals: [], note: '' };
  try { mb = await mediaBuyer(report); } catch (e) { mb.note = 'Media buyer: ' + e.message; }

  const t = report.totals;
  const eur = (n) => (n == null ? 'n/d' : '€' + n.toLocaleString('it-IT'));
  const lines = [
    '📊 MACCHINA LEAD — briefing del mattino (ultimi 7 giorni)',
    '',
    `Spesa ${eur(t.spend)} · Lead ${t.leads} · Qualificati ${t.qualified} · Caldi ${t.hot}`,
    `Costo per lead ${eur(t.cpl)} · per lead qualificato ${eur(t.costPerQualified)}`,
    report.metaError ? `⚠️ Meta: ${report.metaError}` : '',
    '',
    report.analysis,
    '',
    mb.proposals.length
      ? `📢 ${mb.proposals.length} proposte del Media buyer da approvare nel CRM → Macchina Lead.`
      : `📢 Media buyer: nessuna proposta. ${mb.note || ''}`,
  ];
  await notifyOwner(lines.filter((l) => l !== null).join('\n'));
  return { report, mediaBuyer: mb };
}

module.exports = {
  AGENTS_INFO,
  handleIncoming,
  sendHumanMessage,
  setConvStatus,
  getConv,
  listConvs,
  analista,
  mediaBuyer,
  creativo,
  listProposals,
  decideProposal,
  dailyRun,
  REPORT_KEY,
};
