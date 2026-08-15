// Bot Telegram della Boardroom di Crisi.
//
// Setup (una volta sola):
//   1. Su Telegram: @BotFather -> /newbot -> copia il token
//   2. Su Vercel: Settings > Environment Variables > TELEGRAM_BOT_TOKEN = <token> -> Redeploy
//   3. Apri nel browser: https://<tuo-dominio>/api/telegram?setup=1  (registra il webhook)
//   4. Scrivi al bot su Telegram.
//
// Memoria della riunione: di serie usa la memoria del server (puo azzerarsi quando
// il server "si raffredda"). Per memoria permanente (consigliato, gratis):
// crea un database Redis su upstash.com e aggiungi su Vercel
// UPSTASH_REDIS_REST_URL e UPSTASH_REDIS_REST_TOKEN.

const { ADVISORS, ROUND_ORDER, callAdvisor } = require('../lib/advisors');

const MAX_ENTRIES = 40; // interventi tenuti nel verbale inviato al modello

// ── Storage: Upstash Redis (se configurato) con fallback in memoria ──
const mem = global.__tgmem || (global.__tgmem = new Map());

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

// ── Telegram API ──
function tg(method, payload) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  return fetch(`https://api.telegram.org/bot${token}/${method}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((r) => r.json());
}

// Telegram accetta max 4096 caratteri per messaggio
async function sendText(chatId, text, extra) {
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
    await tg('sendMessage', Object.assign({ chat_id: chatId, text: c }, extra || {}));
  }
}

// Le risposte del modello arrivano in markdown: lo ripuliamo per Telegram (testo semplice)
function stripMd(s) {
  return s
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/^\s*[-*]\s+/gm, '• ')
    .replace(/`{1,3}/g, '');
}

const T_KEY = (chatId) => `tg:transcript:${chatId}`;
const OWNER_KEY = 'tg:owner';

const HELP = `👔 RICCARDO — CEO DI CREATIVE MESS ADV

Scrivi un messaggio normale e ti risponde direttamente Riccardo, il CEO AI con mandato di turnaround: decide, prioritizza per impatto sulla cassa e ti dice cosa fare oggi.

Quando serve il tavolo completo, c'e la Boardroom di Crisi (5 advisor AI ispirati ai metodi di Marchionne, Cook, Su, Mulally e Nadella, piu un Moderatore):
• /tavolo + testo -> scegli con i pulsanti a chi mandarlo
• /giro -> giro di tavolo: rispondono tutti e 5 in sequenza
• /sintesi -> il Moderatore produce decisioni + piano 90 giorni
• /riccardo /marchionne /cook /su /mulally /nadella + testo -> parli direttamente con uno
• /verbale -> quanti interventi ha la riunione in corso
• /reset -> chiude la riunione e cancella il verbale

⚠️ Riccardo e gli advisor sono AI, non persone reali. Per debiti, fisco e banche verifica sempre con un commercialista abilitato.

Consiglio: apri con i numeri veri (debiti, scadenze, clienti attivi, costi fissi, cassa). Piu numeri dai, piu le risposte sono chirurgiche.`;

function targetKeyboard() {
  return {
    inline_keyboard: [
      [
        { text: '👔 Riccardo (CEO)', callback_data: 'go:riccardo' },
        { text: '👥 Tutto il tavolo', callback_data: 'go:all' },
      ],
      [
        { text: '🔧 Marchionne', callback_data: 'go:marchionne' },
        { text: '⚙️ Cook', callback_data: 'go:cook' },
      ],
      [
        { text: '🎯 Su', callback_data: 'go:su' },
        { text: '📊 Mulally', callback_data: 'go:mulally' },
      ],
      [
        { text: '🚀 Nadella', callback_data: 'go:nadella' },
        { text: '📋 Sintesi & Piano', callback_data: 'go:moderatore' },
      ],
    ],
  };
}

async function loadTranscript(chatId) {
  return (await kvGet(T_KEY(chatId))) || [];
}
async function saveTranscript(chatId, transcript) {
  await kvSet(T_KEY(chatId), transcript.slice(-MAX_ENTRIES));
}

async function speakOne(chatId, advisorId, transcript, maxTokens) {
  const cfg = ADVISORS[advisorId];
  await tg('sendChatAction', { chat_id: chatId, action: 'typing' });
  try {
    const reply = await callAdvisor(process.env.ANTHROPIC_API_KEY, advisorId, transcript, maxTokens);
    transcript.push({ speaker: cfg.name, text: reply });
    await saveTranscript(chatId, transcript);
    await sendText(chatId, `${cfg.icon} ${cfg.name.toUpperCase()} — ${cfg.title}\n\n${stripMd(reply)}`);
    return true;
  } catch (err) {
    await sendText(chatId, `⚠️ ${cfg.name} non ha risposto: ${err.message}`);
    return false;
  }
}

async function runTarget(chatId, target) {
  const transcript = await loadTranscript(chatId);
  if (!transcript.length) {
    await sendText(chatId, 'La riunione e ancora vuota: scrivimi prima la situazione.');
    return;
  }
  if (target === 'all') {
    await sendText(chatId, '🏛️ Giro di tavolo: i 5 advisor intervengono uno dopo l\'altro...');
    let ok = 0;
    for (const id of ROUND_ORDER) {
      if (await speakOne(chatId, id, transcript, 800)) ok++;
    }
    if (ok === ROUND_ORDER.length) {
      await sendText(chatId, 'Giro di tavolo completato ✅ — quando vuoi il piano scritto, manda /sintesi');
    }
  } else {
    await speakOne(chatId, target, transcript, target === 'moderatore' ? 1500 : 1200);
  }
}

async function checkOwner(chatId) {
  const envOwner = process.env.TELEGRAM_OWNER_ID;
  if (envOwner) return String(chatId) === String(envOwner);
  const owner = await kvGet(OWNER_KEY);
  if (!owner) { await kvSet(OWNER_KEY, String(chatId)); return true; }
  return String(owner) === String(chatId);
}

module.exports = async (req, res) => {
  const token = process.env.TELEGRAM_BOT_TOKEN;

  // ── GET: setup / stato ──
  if (req.method === 'GET') {
    if (!token) {
      return res.status(500).json({ ok: false, error: 'TELEGRAM_BOT_TOKEN non configurato su Vercel (Settings > Environment Variables), poi Redeploy.' });
    }
    if (req.query && req.query.setup) {
      const host = req.headers['x-forwarded-host'] || req.headers.host;
      const url = `https://${host}/api/telegram`;
      const r = await tg('setWebhook', { url, allowed_updates: ['message', 'callback_query'] });
      const me = await tg('getMe', {});
      return res.json({
        ok: r.ok,
        webhook: url,
        telegram_says: r.description || r,
        bot: me.result ? '@' + me.result.username : 'sconosciuto',
        redis: hasRedis() ? 'attivo (memoria permanente)' : 'NON attivo (memoria temporanea — consigliato Upstash)',
      });
    }
    return res.json({ ok: true, info: 'Endpoint Telegram attivo. Apri /api/telegram?setup=1 per registrare il webhook.' });
  }

  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });
  if (!token) return res.status(200).json({ ok: true }); // mai far riprovare Telegram all'infinito

  const update = req.body || {};

  try {
    // ── Pulsanti (callback) ──
    if (update.callback_query) {
      const cb = update.callback_query;
      const chatId = cb.message.chat.id;
      await tg('answerCallbackQuery', { callback_query_id: cb.id });
      if (!(await checkOwner(chatId))) return res.json({ ok: true });
      // togli i pulsanti dal messaggio per non premerli due volte
      await tg('editMessageReplyMarkup', { chat_id: chatId, message_id: cb.message.message_id, reply_markup: { inline_keyboard: [] } });
      const target = (cb.data || '').replace(/^go:/, '');
      if (target === 'all' || ADVISORS[target]) await runTarget(chatId, target);
      return res.json({ ok: true });
    }

    // ── Messaggi ──
    const msg = update.message;
    if (!msg || !msg.text) return res.json({ ok: true });
    const chatId = msg.chat.id;
    const text = msg.text.trim();

    if (!(await checkOwner(chatId))) {
      await sendText(chatId, 'Questa boardroom e riservata al suo proprietario.');
      return res.json({ ok: true });
    }

    if (!process.env.ANTHROPIC_API_KEY) {
      await sendText(chatId, '⚠️ ANTHROPIC_API_KEY non configurata su Vercel: gli advisor non possono rispondere.');
      return res.json({ ok: true });
    }

    // Comandi
    const cmdMatch = text.match(/^\/([a-z]+)(?:@\w+)?\s*([\s\S]*)$/i);
    if (cmdMatch) {
      const cmd = cmdMatch[1].toLowerCase();
      const rest = cmdMatch[2].trim();

      if (cmd === 'start' || cmd === 'help') {
        await sendText(chatId, HELP);
        return res.json({ ok: true });
      }
      if (cmd === 'reset') {
        await kvDel(T_KEY(chatId));
        await sendText(chatId, 'Riunione chiusa e verbale cancellato. Quando vuoi si riparte: scrivimi la situazione.');
        return res.json({ ok: true });
      }
      if (cmd === 'verbale') {
        const t = await loadTranscript(chatId);
        await sendText(chatId, `Riunione in corso: ${t.length} interventi nel verbale.` + (hasRedis() ? '' : '\n(memoria temporanea: configura Upstash per non perdere il verbale)'));
        return res.json({ ok: true });
      }
      if (cmd === 'tavolo') {
        const t = await loadTranscript(chatId);
        if (rest) {
          t.push({ speaker: 'Roberto (Presidente)', text: rest });
          await saveTranscript(chatId, t);
        }
        if (!t.length) {
          await sendText(chatId, 'La riunione e ancora vuota: scrivi /tavolo seguito dalla situazione.');
          return res.json({ ok: true });
        }
        await tg('sendMessage', { chat_id: chatId, text: 'A chi lo mando?', reply_markup: targetKeyboard() });
        return res.json({ ok: true });
      }
      if (cmd === 'giro' || cmd === 'tutti') {
        if (rest) {
          const t = await loadTranscript(chatId);
          t.push({ speaker: 'Roberto (Presidente)', text: rest });
          await saveTranscript(chatId, t);
        }
        await runTarget(chatId, 'all');
        return res.json({ ok: true });
      }
      if (cmd === 'sintesi' || cmd === 'piano') {
        if (rest) {
          const t = await loadTranscript(chatId);
          t.push({ speaker: 'Roberto (Presidente)', text: rest });
          await saveTranscript(chatId, t);
        }
        await runTarget(chatId, 'moderatore');
        return res.json({ ok: true });
      }
      if (ADVISORS[cmd]) {
        const t = await loadTranscript(chatId);
        if (rest) t.push({ speaker: `Roberto (Presidente) (rivolto ad ${ADVISORS[cmd].name})`, text: rest });
        await saveTranscript(chatId, t);
        await runTarget(chatId, cmd);
        return res.json({ ok: true });
      }
      await sendText(chatId, 'Comando non riconosciuto. Manda /help per la lista.');
      return res.json({ ok: true });
    }

    // Messaggio normale: risponde direttamente Riccardo, il CEO
    const transcript = await loadTranscript(chatId);
    transcript.push({ speaker: 'Roberto (Presidente)', text });
    await saveTranscript(chatId, transcript);
    await speakOne(chatId, 'riccardo', transcript, 1200);
    return res.json({ ok: true });
  } catch (err) {
    // rispondi comunque 200: se Telegram riceve errore, rimanda lo stesso update in loop
    try {
      const chatId = (update.message && update.message.chat.id) || (update.callback_query && update.callback_query.message.chat.id);
      if (chatId) await sendText(chatId, '⚠️ Errore imprevisto: ' + err.message);
    } catch (e) { /* niente */ }
    return res.status(200).json({ ok: true });
  }
};

module.exports.config = { maxDuration: 60 };
