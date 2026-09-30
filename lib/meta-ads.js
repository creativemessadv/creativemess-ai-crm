// Meta Marketing API: metriche per annuncio (lettura) e modifiche approvate (budget, pausa).

const GRAPH = () => `https://graph.facebook.com/${process.env.META_GRAPH_VERSION || 'v23.0'}`;
const configured = () => !!(process.env.META_ADS_TOKEN && process.env.META_AD_ACCOUNT_ID);
const writeEnabled = () => process.env.META_ADS_WRITE === '1';
const maxDailyBudget = () => parseFloat(process.env.META_MAX_DAILY_BUDGET || '50');

const account = () => {
  const id = String(process.env.META_AD_ACCOUNT_ID || '');
  return id.startsWith('act_') ? id : `act_${id}`;
};

async function graphGet(path, params) {
  const qs = new URLSearchParams(Object.assign({ access_token: process.env.META_ADS_TOKEN }, params));
  const r = await fetch(`${GRAPH()}/${path}?${qs}`);
  const d = await r.json();
  if (!r.ok || d.error) throw new Error('Meta Ads: ' + ((d.error && d.error.message) || r.status));
  return d;
}

async function graphPost(path, params) {
  const body = new URLSearchParams(Object.assign({ access_token: process.env.META_ADS_TOKEN }, params));
  const r = await fetch(`${GRAPH()}/${path}`, { method: 'POST', body });
  const d = await r.json();
  if (!r.ok || d.error) throw new Error('Meta Ads: ' + ((d.error && d.error.message) || r.status));
  return d;
}

const CONV_ACTIONS = [
  'onsite_conversion.messaging_conversation_started_7d',
  'onsite_conversion.total_messaging_connection',
];

// Metriche per annuncio sul periodo (default ultimi 7 giorni)
async function adInsights(datePreset = 'last_7d') {
  const d = await graphGet(`${account()}/insights`, {
    level: 'ad',
    date_preset: datePreset,
    fields: 'ad_id,ad_name,adset_id,adset_name,campaign_name,spend,impressions,clicks,ctr,cpm,frequency,actions',
    limit: '200',
  });
  return (d.data || []).map((row) => {
    const acts = row.actions || [];
    const conv = CONV_ACTIONS.map((t) => acts.find((a) => a.action_type === t)).find(Boolean);
    return {
      adId: row.ad_id,
      adName: row.ad_name,
      adsetId: row.adset_id,
      adsetName: row.adset_name,
      campaign: row.campaign_name,
      spend: parseFloat(row.spend || 0),
      impressions: parseInt(row.impressions || 0, 10),
      clicks: parseInt(row.clicks || 0, 10),
      ctr: parseFloat(row.ctr || 0),
      cpm: parseFloat(row.cpm || 0),
      frequency: parseFloat(row.frequency || 0),
      conversations: conv ? parseInt(conv.value, 10) : 0,
    };
  });
}

// Budget giornalieri degli adset (Meta li restituisce in centesimi)
async function adsets() {
  const d = await graphGet(`${account()}/adsets`, {
    fields: 'id,name,daily_budget,effective_status',
    limit: '200',
  });
  return (d.data || []).map((s) => ({
    id: s.id,
    name: s.name,
    dailyBudget: s.daily_budget ? parseInt(s.daily_budget, 10) / 100 : null,
    status: s.effective_status,
  }));
}

async function setAdsetBudget(adsetId, euros) {
  const cents = Math.round(Math.min(euros, maxDailyBudget()) * 100);
  return graphPost(adsetId, { daily_budget: String(cents) });
}

async function setStatus(objectId, status) {
  return graphPost(objectId, { status });
}

module.exports = { configured, writeEnabled, maxDailyBudget, adInsights, adsets, setAdsetBudget, setStatus };
