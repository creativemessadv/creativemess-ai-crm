// CM WAR — la direzione su Telegram: 3 bot, 3 chat.
//
//   • Bot "War Room"  -> parlano entrambi i manager (Briatore poi Cook), reagendo l'uno all'altro
//   • Bot "Briatore"  -> linea diretta con il manager Vendite & Business
//   • Bot "Cook"      -> linea diretta con il manager Operazioni & Cassa
//
// Setup (una volta sola):
//   1. Su Telegram: @BotFather -> /newbot (tre volte, un bot per chat) -> copia i 3 token
//   2. Su Vercel (Settings > Environment Variables), aggiungi e poi Redeploy:
//        TELEGRAM_TOKEN_WAR       = token del bot della War Room
//        TELEGRAM_TOKEN_BRIATORE  = token del bot di Briatore
//        TELEGRAM_TOKEN_COOK      = token del bot di Cook
//   3. Registra i webhook aprendo nel browser:
//        https://<dominio>/api/war?setup=war
//        https://<dominio>/api/war?setup=briatore
//        https://<dominio>/api/war?setup=cook
//   4. Scrivi ai bot su Telegram. Il primo che scrive a ogni bot ne diventa il proprietario.
//
// Stato: https://<dominio>/api/war   (mostra quali bot sono configurati)

const { MANAGERS, WAR_ORDER, callManager } = require('../lib/managers');

const MAX_ENTRIES = 40; // messaggi tenuti nella memoria inviata al modello

const BOTS = {
  war: { env: 'TELEGRAM_TOKEN_WAR', label: 'War Room (Briatore + Cook)' },
  briatore: { env: 'TELEGRAM_TOKEN_BRIATORE', label: 'Linea diretta Briatore' },
  cook: { env: 'TELEGRAM_TOKEN_COOK', label: 'Linea diretta Cook' },
};
const botToken = (botId) => process.env[(BOTS[botId] || {}).env] || null;

// ── Storage: Upstash Redis (se configurato) con fallback in memoria ──
const mem = global.__warmem || (global.__warmem = new Map());

async function redis(cmd) {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  const r = await fetch(url, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'content-type': 'application/json' },
    body: JSON.stringify(cmd),
  });
  const d = await r.json();
  if (d.error) throw new Error('Redis: ' + d.error);
  return d;
}
const hasRedis = () => !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);

async function kvGet(key) {
  if (!hasRedis()) return mem.get(key) || null;
  const d = await redis(['GET', key]);
  return d && d.result ? JSON.parse(d.result) : null;
}
async function kvSet(key, val) {
  if (!hasRedis()) { mem.set(key, val); return; }
  await redis(['SET', key, JSON.stringify(val)]);
}
async function kvDel(key) {
  if (!hasRedis()) { mem.delete(key); return; }
  await redis(['DEL', key]);
}

const T_KEY = (botId, chatId) => `war:${botId}:transcript:${chatId}`;
const OWNER_KEY = (botId) => `war:${botId}:owner`;

// ── Telegram API ──
function tg(botId, method, payload) {
  return fetch(`https://api.telegram.org/bot${botToken(botId)}/${method}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((r) => r.json());
}

// Telegram accetta max 4096 caratteri per messaggio
async function sendText(botId, chatId, text) {
  const chunks = [];
  let t = text;
  while (t.length > 3900) {
    let cut = t.lastIndexOf('\n', 3900);
    if (cut < 500) cut = 3900;
    chunks.push(t.slice(0, cut));
    t = t.slice(cut);
  }
  chunks.push(t);
  for (const c of chunks) {
    await tg(botId, 'sendMessage', { chat_id: chatId, text: c });
  }
}

// Le risposte del modello arrivano in markdown: testo semplice per Telegram
function stripMd(s) {
  return s
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/`{1,3}/g, '');
}

const HELP = {
  war: `⚔️ CM WAR — WAR ROOM

Qui dentro ci siamo io, Briatore (Vendite & Business) e Cook (Operazioni & Cassa): la direzione al completo.
Scrivi e rispondiamo entrambi, uno dopo l'altro — e se non siamo d'accordo tra noi, lo sentirai.

• Scrivi normalmente -> intervengono entrambi i manager
• /verbale -> quanti messaggi ha la riunione in corso
• /reset -> chiude la riunione e azzera la memoria

⚠️ Siamo manager AI ispirati a metodi di gestione pubblicamente noti, non le persone reali.
Per debiti, fisco e banche verifica sempre con un commercialista abilitato.

Porta i numeri veri (cassa, debiti, scadenze, clienti, costi): senza numeri non si decide.`,
  briatore: `🐆 CM WAR — LINEA DIRETTA CON BRIATORE (Vendite & Business)

Qui parli solo con me. Fatturato, clienti, pricing, trattative, network: si vende e si incassa.
Ti dico quello che penso, non quello che vuoi sentirti dire.

• Scrivi normalmente -> ti rispondo io
• /verbale -> lunghezza della conversazione in memoria
• /reset -> azzera la conversazione

⚠️ Sono un manager AI ispirato a un metodo di gestione pubblicamente noto, non la persona reale.`,
  cook: `⚙️ CM WAR — LINEA DIRETTA CON COOK (Operazioni & Cassa)

Qui parli solo con me. Cash flow, margini, costi da tagliare, priorita, scadenze: la macchina deve reggere.
Senza numeri esatti non si decide niente: portali.

• Scrivi normalmente -> ti rispondo io
• /verbale -> lunghezza della conversazione in memoria
• /reset -> azzera la conversazione

⚠️ Sono un manager AI ispirato a un metodo di gestione pubblicamente noto, non la persona reale.`,
};

async function loadTranscript(botId, chatId) {
  return (await kvGet(T_KEY(botId, chatId))) || [];
}
async function saveTranscript(botId, chatId, transcript) {
  await kvSet(T_KEY(botId, chatId), transcript.slice(-MAX_ENTRIES));
}

async function speak(botId, chatId, managerId, transcript, room) {
  const cfg = MANAGERS[managerId];
  await tg(botId, 'sendChatAction', { chat_id: chatId, action: 'typing' });
  try {
    const reply = await callManager(process.env.ANTHROPIC_API_KEY, managerId, transcript, 4000, room);
    transcript.push({ speaker: cfg.name, text: reply });
    await saveTranscript(botId, chatId, transcript);
    await sendText(botId, chatId, `${cfg.icon} ${cfg.name.toUpperCase()} — ${cfg.title}\n\n${stripMd(reply)}`);
    return true;
  } catch (err) {
    await sendText(botId, chatId, `⚠️ ${cfg.name} non ha risposto: ${err.message}`);
    return false;
  }
}

async function checkOwner(botId, chatId) {
  const owner = await kvGet(OWNER_KEY(botId));
  if (!owner) { await kvSet(OWNER_KEY(botId), String(chatId)); return true; }
  return String(owner) === String(chatId);
}

module.exports = async (req, res) => {
  const q = req.query || {};

  // ── GET: stato / setup ──
  if (req.method === 'GET') {
    if (q.setup && BOTS[q.setup]) {
      const botId = q.setup;
      if (!botToken(botId)) {
        return res.status(500).json({ ok: false, error: `${BOTS[botId].env} non configurato su Vercel (Settings > Environment Variables), poi Redeploy.` });
      }
      const host = req.headers['x-forwarded-host'] || req.headers.host;
      const url = `https://${host}/api/war?bot=${botId}`;
      const r = await tg(botId, 'setWebhook', { url, allowed_updates: ['message'] });
      const me = await tg(botId, 'getMe', {});
      return res.json({
        ok: r.ok,
        chat: BOTS[botId].label,
        webhook: url,
        telegram_says: r.description || r,
        bot: me.result ? '@' + me.result.username : 'sconosciuto',
        redis: hasRedis() ? 'attivo (memoria permanente)' : 'NON attivo (memoria temporanea — consigliato Upstash)',
      });
    }
    const stato = {};
    for (const [id, b] of Object.entries(BOTS)) {
      stato[b.label] = botToken(id) ? `token ok — registra con /api/war?setup=${id}` : `manca la variabile ${b.env} su Vercel`;
    }
    return res.json({ ok: true, info: 'CM WAR attivo. Tre bot: war, briatore, cook.', bots: stato });
  }

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const botId = q.bot;
  if (!BOTS[botId] || !botToken(botId)) return res.status(200).json({ ok: true });

  const update = req.body || {};

  try {
    const msg = update.message;
    if (!msg || !msg.text) return res.json({ ok: true });
    const chatId = msg.chat.id;
    const text = msg.text.trim();

    if (!(await checkOwner(botId, chatId))) {
      await sendText(botId, chatId, 'Questa direzione e riservata al Presidente.');
      return res.json({ ok: true });
    }

    if (!process.env.ANTHROPIC_API_KEY) {
      await sendText(botId, chatId, '⚠️ ANTHROPIC_API_KEY non configurata su Vercel: i manager non possono rispondere.');
      return res.json({ ok: true });
    }

    // Comandi
    const cmdMatch = text.match(/^\/([a-z]+)(?:@\w+)?\s*([\s\S]*)$/i);
    if (cmdMatch) {
      const cmd = cmdMatch[1].toLowerCase();
      const rest = cmdMatch[2].trim();

      if (cmd === 'start' || cmd === 'help') {
        await sendText(botId, chatId, HELP[botId]);
        return res.json({ ok: true });
      }
      if (cmd === 'reset') {
        await kvDel(T_KEY(botId, chatId));
        await sendText(botId, chatId, 'Memoria azzerata. Si riparte: scrivimi la situazione.');
        return res.json({ ok: true });
      }
      if (cmd === 'verbale') {
        const t = await loadTranscript(botId, chatId);
        await sendText(botId, chatId, `Conversazione in corso: ${t.length} messaggi in memoria.` + (hasRedis() ? '' : '\n(memoria temporanea: configura Upstash per non perderla)'));
        return res.json({ ok: true });
      }
      if (!rest) {
        await sendText(botId, chatId, 'Comando non riconosciuto. Manda /help.');
        return res.json({ ok: true });
      }
      // comando sconosciuto con testo: trattalo come messaggio normale
    }

    // Messaggio normale
    const transcript = await loadTranscript(botId, chatId);
    transcript.push({ speaker: 'Roberto (Presidente)', text });
    await saveTranscript(botId, chatId, transcript);

    if (botId === 'war') {
      for (const id of WAR_ORDER) {
        await speak(botId, chatId, id, transcript, 'war');
      }
    } else {
      await speak(botId, chatId, botId, transcript, 'direct');
    }
    return res.json({ ok: true });
  } catch (err) {
    // rispondi comunque 200: se Telegram riceve errore, rimanda lo stesso update in loop
    try {
      const chatId = update.message && update.message.chat.id;
      if (chatId) await sendText(botId, chatId, '⚠️ Errore imprevisto: ' + err.message);
    } catch (e) { /* niente */ }
    return res.status(200).json({ ok: true });
  }
};

module.exports.config = { maxDuration: 60 };
