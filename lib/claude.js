// Chiamate al modello per la Macchina Lead, con retry su rate limit / sovraccarico.
//   ask()        -> testo libero
//   askStruct()  -> oggetto JSON validato dallo schema (tool use forzato)

const MODEL = () => process.env.AI_MODEL || 'claude-sonnet-5';
const MODEL_FAST = () => process.env.AI_MODEL_FAST || 'claude-haiku-4-5-20251001';

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

async function request(body) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY non configurata su Vercel.');
  let lastErr = 'Errore sconosciuto';
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) await sleep(attempt === 1 ? 2000 : 6000);
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (r.ok) return data;
    lastErr = (data && data.error && data.error.message) || `Errore API Anthropic (HTTP ${r.status})`;
    // 429 = rate limit, 529 = sovraccarico: vale la pena riprovare; altri errori no
    if (r.status !== 429 && r.status !== 529) break;
  }
  throw new Error(lastErr);
}

// messages: [{role:'user'|'assistant', content}]
async function ask({ system, messages, maxTokens = 1500, fast = false }) {
  const data = await request({ model: fast ? MODEL_FAST() : MODEL(), max_tokens: maxTokens, system, messages });
  const text = (data.content || [])
    .filter((b) => b.type === 'text' && b.text)
    .map((b) => b.text)
    .join('\n\n')
    .trim();
  if (!text) throw new Error(`Risposta vuota dal modello (stop_reason: ${data.stop_reason || 'n/d'}).`);
  return text;
}

// Forza il modello a "chiamare" un tool: l'input del tool e il nostro oggetto strutturato.
async function askStruct({ system, messages, name, description, schema, maxTokens = 2000, fast = false }) {
  const data = await request({
    model: fast ? MODEL_FAST() : MODEL(),
    max_tokens: maxTokens,
    system,
    messages,
    tools: [{ name, description, input_schema: schema }],
    tool_choice: { type: 'tool', name },
  });
  const block = (data.content || []).find((b) => b.type === 'tool_use' && b.name === name);
  if (!block) throw new Error(`Il modello non ha prodotto l'output strutturato (stop_reason: ${data.stop_reason || 'n/d'}).`);
  return block.input;
}

module.exports = { ask, askStruct };
