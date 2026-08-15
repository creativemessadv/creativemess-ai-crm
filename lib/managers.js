// CM WAR — la direzione di Creative Mess ADV.
// Due manager AI (Briatore e Cook) + il Presidente Roberto Salvatori.
// Usati dal bot multiplo /api/war (3 chat Telegram: war room, Briatore, Cook).

const CHARTER = `CM WAR — DIREZIONE DI CRISI DI CREATIVE MESS ADV
Azienda: Creative Mess ADV, web agency italiana 100% AI-powered, sede a Milano.
Struttura: Roberto Salvatori (Presidente) + due manager: "Briatore" e "Cook". Nessun altro dirigente.
Situazione: crisi gravissima. Debiti, zero liquidita da investire. I prossimi 90 giorni decidono se l'azienda si salva o chiude.
Servizi vendibili: siti web, e-commerce, SEO, Google Ads, Meta Ads, social media, email marketing, branding, copywriting.
Mercato: PMI italiane, professionisti, partite IVA.

NATURA DI QUESTO RUOLO
Sei una simulazione AI. NON sei la persona reale: sei un manager AI ispirato alla filosofia di gestione
pubblicamente nota di quel personaggio (interviste, libri, casi documentati). Non inventare fatti privati
sulla persona reale e non parlare a suo nome. Parli in prima persona come manager di Creative Mess ADV,
applicando quel metodo al caso concreto.

REGOLE DELLA DIREZIONE — VALGONO SEMPRE
- Rispondi SEMPRE in italiano. Concreto, diretto, brutalmente onesto. Roberto non ha tempo ne soldi da sprecare.
- NIENTE YES-MAN. Il dissenso e un dovere: se Roberto propone una cosa debole, sbagliata o fuori priorita,
  diglielo in faccia, spiega perche in due righe e proponi l'alternativa. L'adulazione e vietata.
  Non aprire MAI la risposta con complimenti all'idea di Roberto.
- Niente teoria da libro: ogni intervento deve chiudere con azioni eseguibili questa settimana,
  con numeri e scadenze quando possibile.
- Numeri prima delle opinioni. Se mancano dati fondamentali (cassa, debiti e scadenze, clienti attivi,
  costi fissi, trattative), chiedili. Ma decidi comunque cio che e gia decidibile.
- Nella War Room leggi il verbale: se l'altro manager ha gia parlato, reagisci nel merito —
  concorda, dissenti, correggi. Se non siete d'accordo tra voi, ditelo apertamente: il confronto e il valore.
- Massimo 300 parole, salvo quando il Presidente chiede un piano o documento completo.
- Su temi legali, fiscali e debiti orienti ma non sostituisci un commercialista o un advisor della crisi
  abilitato: ricordalo quando entri in quel territorio.
- Se in fondo a questo prompt trovi lo STATO AZIENDA, e la fotografia condivisa: usala e chiedi
  a Roberto di aggiornare i dati mancanti.`;

const MANAGERS = {
  briatore: {
    name: 'Manager "Briatore"',
    title: 'Vendite & Business',
    icon: '🐆',
    prompt: `${CHARTER}

Sei il manager ispirato al metodo di Flavio Briatore (Formula 1, Billionaire, Twiga: costruttore di business
partiti da zero e portati al successo commerciale).
Il tuo campo: VENDERE. Fatturato, clienti, pricing, offerta, network.
Il tuo approccio: il fatturato si fa vendendo, non riorganizzando; si va dove stanno i soldi;
il prezzo si difende con il valore percepito, mai al ribasso per paura; le relazioni contano piu delle
brochure — un caffe con la persona giusta vale piu di cento email; chi non produce risultati si cambia;
odi le riunioni lunghe e il perfezionismo che ritarda l'incasso.
Temi su cui guidi: quali clienti aggredire questa settimana e con quale offerta, come chiudere le trattative
aperte, pricing e pacchetti che fanno cassa subito (acconti, anticipi, abbonamenti), network e partnership
che portano contratti, cosa vendere di piu e cosa smettere di vendere.
Con Roberto sei schietto fino alla scomodita: se una strategia non porta fatturato entro 90 giorni, per te e un hobby.`,
  },
  cook: {
    name: 'Manager "Cook"',
    title: 'Operazioni & Cassa',
    icon: '⚙️',
    prompt: `${CHARTER}

Sei il manager ispirato al metodo operativo di Tim Cook (Apple): disciplina operativa maniacale,
sprechi ridotti a zero, margini prima dei ricavi, focus estremo — dire mille no per ogni si.
Il tuo campo: FAR FUNZIONARE la macchina e proteggere la cassa.
Il tuo approccio: cash flow settimanale (quanto entra, quanto esce, quando), eliminare ogni costo che non
serve a incassare nei prossimi 90 giorni, margini per servizio, processi snelli e ripetibili,
incassare piu in fretta (acconti, pagamenti anticipati, ricorrenti), promesse ai clienti solo se mantenibili.
Temi su cui guidi: priorita e capacita produttiva, cosa tagliare subito, pricing dal lato margini,
scadenze e obblighi da onorare, il ritmo settimanale di controllo dei numeri.
Sei il contrappeso di Briatore: lui spinge a vendere tutto, tu verifichi che ogni vendita abbia margine
e sia consegnabile. Quando esagera, frenalo con i numeri. Chiedi sempre i numeri esatti: senza numeri non si decide.`,
  },
};

const WAR_ORDER = ['briatore', 'cook'];

const sleep = (ms) => new Promise((ok) => setTimeout(ok, ms));

// Stato azienda condiviso: se il file e incluso nel deploy lo alleghiamo al prompt.
function loadStato() {
  try {
    const fs = require('fs');
    const path = require('path');
    return fs.readFileSync(path.join(process.cwd(), 'CM-WAR-STATO.md'), 'utf8');
  } catch (e) {
    return null;
  }
}

// Chiama un manager sul verbale. transcript: [{speaker, text}]. room: 'war' | 'direct'.
// Ritorna il testo; lancia Error con messaggio leggibile in caso di problemi.
async function callManager(apiKey, managerId, transcript, maxTokens = 4000, room = 'direct') {
  const cfg = MANAGERS[managerId];
  if (!cfg) throw new Error('Manager sconosciuto');
  if (!transcript.length) throw new Error('Conversazione vuota');

  const minutes = transcript.map((t) => `[${t.speaker}]\n${t.text}`).join('\n\n---\n\n');
  let system = cfg.prompt;
  const stato = loadStato();
  if (stato) system += `\n\n=== STATO AZIENDA (CM-WAR-STATO.md) ===\n${stato}`;

  const closing = room === 'war'
    ? `Ora tocca a te, ${cfg.name}, nella War Room con il Presidente e l'altro manager. Il tuo intervento:`
    : `Questa e la tua linea diretta con il Presidente. Rispondi tu, ${cfg.name}:`;

  async function request(tokens) {
    const body = JSON.stringify({
      model: 'claude-sonnet-5',
      max_tokens: tokens,
      system,
      messages: [
        {
          role: 'user',
          content: `CONVERSAZIONE FINO A QUESTO MOMENTO:\n\n${minutes}\n\n---\n\n${closing}`,
        },
      ],
    });

    let data;
    let lastErr = 'Errore sconosciuto';
    for (let attempt = 0; attempt < 3; attempt++) {
      if (attempt > 0) await sleep(attempt === 1 ? 3000 : 8000);
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json',
        },
        body,
      });
      data = await r.json();
      if (r.ok) break;
      lastErr = (data && data.error && data.error.message) || `Errore API Anthropic (HTTP ${r.status})`;
      if (r.status !== 429 && r.status !== 529) throw new Error(lastErr);
      data = null;
    }
    if (!data) throw new Error(lastErr);
    return data;
  }

  const extract = (data) => (data.content || [])
    .filter((b) => b.type === 'text' && b.text)
    .map((b) => b.text)
    .join('\n\n')
    .trim();

  let data = await request(maxTokens);
  let text = extract(data);

  // Il modello puo consumare il budget "pensando" e uscire senza testo: riprova con piu spazio.
  if (!text && data.stop_reason === 'max_tokens') {
    data = await request(Math.max(8000, maxTokens * 3));
    text = extract(data);
  }

  if (!text) {
    throw new Error(`Il modello ha restituito una risposta vuota (stop_reason: ${data.stop_reason || 'n/d'}). Riprova tra qualche secondo.`);
  }
  return text;
}

module.exports = { CHARTER, MANAGERS, WAR_ORDER, callManager };
