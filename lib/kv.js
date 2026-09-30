// Memoria condivisa della Macchina Lead: Upstash Redis (se configurato) con ripiego in memoria.
// In memoria i dati si perdono quando il server "si raffredda": va bene solo per le prove.

const mem = global.__leadmem || (global.__leadmem = new Map());

const hasRedis = () => !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);

async function redis(cmd) {
  const r = await fetch(process.env.UPSTASH_REDIS_REST_URL, {
    method: 'POST',
    headers: { Authorization: `Bearer ${process.env.UPSTASH_REDIS_REST_TOKEN}`, 'content-type': 'application/json' },
    body: JSON.stringify(cmd),
  });
  const d = await r.json();
  if (d.error) throw new Error('Redis: ' + d.error);
  return d.result;
}

async function get(key) {
  if (!hasRedis()) return mem.has(key) ? mem.get(key) : null;
  const v = await redis(['GET', key]);
  return v ? JSON.parse(v) : null;
}

async function mget(keys) {
  if (!keys.length) return [];
  if (!hasRedis()) return keys.map((k) => (mem.has(k) ? mem.get(k) : null));
  const vals = await redis(['MGET', ...keys]);
  return (vals || []).map((v) => (v ? JSON.parse(v) : null));
}

async function set(key, val) {
  if (!hasRedis()) { mem.set(key, val); return; }
  await redis(['SET', key, JSON.stringify(val)]);
}

async function del(key) {
  if (!hasRedis()) { mem.delete(key); return; }
  await redis(['DEL', key]);
}

// Imposta la chiave solo se non esiste (per deduplicare i webhook). Ritorna true se l'ha impostata.
async function setOnce(key, ttlSeconds) {
  if (!hasRedis()) {
    if (mem.has(key)) return false;
    mem.set(key, 1);
    return true;
  }
  return (await redis(['SET', key, '1', 'NX', 'EX', String(ttlSeconds)])) === 'OK';
}

// Indice ordinato per punteggio (usiamo il timestamp): il piu recente per primo.
async function zadd(key, score, member) {
  if (!hasRedis()) {
    const z = mem.get(key) || new Map();
    z.set(member, score);
    mem.set(key, z);
    return;
  }
  await redis(['ZADD', key, String(score), member]);
}

async function zrevrange(key, start, stop) {
  if (!hasRedis()) {
    const z = mem.get(key) || new Map();
    return [...z.entries()].sort((a, b) => b[1] - a[1]).slice(start, stop + 1).map((e) => e[0]);
  }
  return (await redis(['ZREVRANGE', key, String(start), String(stop)])) || [];
}

module.exports = { hasRedis, get, mget, set, del, setOnce, zadd, zrevrange };
