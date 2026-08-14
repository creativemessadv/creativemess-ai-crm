const { ADVISORS, callAdvisor } = require('../lib/advisors');

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  const { advisor, transcript = [] } = req.body || {};
  const cfg = ADVISORS[advisor];
  if (!cfg) return res.status(400).json({ error: 'Advisor sconosciuto' });
  if (!transcript.length) return res.status(400).json({ error: 'Verbale vuoto' });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return res.status(500).json({
      error: 'ANTHROPIC_API_KEY non configurata. Su Vercel: Settings > Environment Variables > aggiungi ANTHROPIC_API_KEY, poi Redeploy.',
    });
  }

  try {
    const reply = await callAdvisor(apiKey, advisor, transcript);
    res.json({ reply, advisor: cfg.name, title: cfg.title });
  } catch (err) {
    res.status(502).json({ error: err.message });
  }
};

module.exports.config = { maxDuration: 60 };
