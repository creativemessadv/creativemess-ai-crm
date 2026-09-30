# Macchina Lead — Meta Ads → WhatsApp → CRM, guidata da agenti AI

Ispirazione: IVOT Agent (ivotagent.com). IVOT vende "29 agenti coordinati da un manager AI":
l'utente approva annunci generati dall'AI, gli annunci Click-to-WhatsApp portano i contatti in chat,
un agente WhatsApp risponde in pochi secondi 24/7, qualifica, fissa appuntamenti e passa la chat
a un umano quando serve; tutto finisce in un CRM, e un briefing giornaliero propone azioni
approvabili con un tocco.

Qui costruiamo lo stesso circuito dentro il CRM di Creative Mess ADV, con **5 agenti** invece di 29,
perche il valore sta nel circuito chiuso, non nel numero di agenti.

## Il circuito

```
 ┌───────────┐ variazioni  ┌─────────────┐  proposte budget/pausa  ┌──────────────┐
 │ CREATIVO  │────────────▶│ APPROVAZIONE│◀────────────────────────│ MEDIA BUYER  │
 └─────▲─────┘             │  (Roberto,  │                         └──────▲───────┘
       │ cosa funziona     │  nel CRM)   │── esegue su Meta API ──▶ Meta Ads │
       │                   └─────────────┘                                │
 ┌─────┴─────┐  report: costo per lead QUALIFICATO per annuncio    ┌──────┴───────┐
 │ ANALISTA  │◀────────────────────────────────────────────────────│ dati Meta +  │
 └───────────┘                                                     │ lead del CRM │
                                                                   └──────▲───────┘
 Annuncio Click-to-WhatsApp ──▶ messaggio WhatsApp (con ad_id)            │
        ┌──────────────────────┐   profilo + punteggio   ┌──────────────┐ │
        │ VENDITORE WHATSAPP   │◀───────────────────────▶│ QUALIFICATORE│─┘
        │ risponde in secondi  │                         │ scheda lead  │──▶ Airtable PIPELINE
        └──────────────────────┘                         └──────────────┘    + avviso Telegram
```

La differenza chiave rispetto a una normale campagna: ogni conversazione WhatsApp porta con se
l'**ID dell'annuncio** che l'ha generata (campo `referral` di Meta). Quindi l'Analista non ottimizza
sul "costo per messaggio" (metrica di Meta) ma sul **costo per lead qualificato** (metrica nostra,
che Meta non conosce). Il Media buyer sposta budget sugli annunci che portano clienti veri.

## I 5 agenti

| Agente | Quando lavora | Input | Output | Autonomia |
|---|---|---|---|---|
| 💬 **Venditore WhatsApp** | a ogni messaggio in arrivo | conversazione, scheda lead, annuncio di provenienza | risposta WhatsApp | autonomo, con passaggio a umano |
| 🎯 **Qualificatore** | dopo ogni scambio | conversazione | scheda strutturata: servizio, settore, citta, budget, tempi, decisore, punteggio 0-100, stadio | autonomo (solo dati) |
| 📊 **Analista** | ogni mattina + su richiesta | metriche Meta per annuncio + lead per annuncio | report: CPL, costo per lead qualificato, vincenti/perdenti | autonomo (solo lettura) |
| 📢 **Media buyer** | dopo l'Analista | report dell'Analista | proposte: alza/abbassa budget, metti in pausa | **serve approvazione** |
| 🎨 **Creativo** | su richiesta o quando un annuncio si esaurisce | offerta, target, annunci vincenti | varianti Click-to-WhatsApp: testo, titolo, messaggio precompilato, concept immagine | **serve approvazione** |

Regola d'oro (come IVOT): gli agenti che **parlano coi clienti** e **leggono dati** lavorano da soli;
gli agenti che **spendono soldi** o **pubblicano** propongono, e Roberto approva con un clic.

## Qualificazione

Criteri (adattati a una web agency che vende a PMI):
- **Bisogno**: quale servizio (sito, e-commerce, SEO, Ads, social...)
- **Budget**: mensile o una tantum dichiarato — confrontato con i prezzi di listino
- **Tempi**: entro 30 giorni / 1-3 mesi / senza fretta
- **Decisore**: parla il titolare o qualcuno che decide?
- **Fit**: settore e citta (PMI italiana = target)

Stadi: `nuovo` → `in_qualifica` → `caldo` | `tiepido` | `freddo` | `non_target`.
Quando un lead diventa **caldo** (punteggio ≥ 70):
1. il Venditore propone una call con Roberto;
2. il lead viene scritto in Airtable `PIPELINE` (fase "Lead");
3. Roberto riceve un avviso su Telegram con la scheda.

Passaggio a umano: se il cliente chiede una persona, se si arrabbia, o se Roberto clicca
"Prendo io" nel CRM, il bot smette di rispondere su quella chat. Roberto puo scrivere dal CRM.

## Regole di sicurezza e conformita

- **Trasparenza**: il primo messaggio dichiara che risponde l'assistente digitale di Creative Mess ADV.
- **STOP**: se il cliente scrive STOP/basta/non scrivermi, il bot conferma e non scrive piu.
- **Finestra 24 ore di WhatsApp**: fuori dalla finestra si possono mandare solo template approvati.
  Il bot risponde solo a messaggi in arrivo, quindi e sempre dentro la finestra.
- **Niente promesse**: il Venditore cita solo le fasce di prezzo di listino, mai sconti o garanzie.
- **Budget**: il Media buyer non puo proporre variazioni oltre ±30% per volta ne superare il tetto
  giornaliero `META_MAX_DAILY_BUDGET`. Le modifiche su Meta partono solo se `META_ADS_WRITE=1`;
  altrimenti le proposte approvate restano "da eseguire a mano".
- **Firma dei webhook**: se `META_APP_SECRET` e impostato, ogni webhook WhatsApp viene verificato.
- **API del CRM protette**: `/api/agents` richiede la chiave `CRM_API_KEY` (va inserita in ⚙️ Configurazione).

## Architettura tecnica (coerente con il repo)

Stesso stile degli endpoint esistenti: funzioni Vercel senza dipendenze npm, `fetch` nativo,
Upstash Redis per la memoria (con ripiego in memoria per le prove), Airtable come CRM.

| File | Ruolo |
|---|---|
| `lib/kv.js` | memoria condivisa (Redis Upstash o RAM) |
| `lib/claude.js` | chiamata al modello con retry e output strutturato (tool use) |
| `lib/airtable.js` | scrittura lato server su Airtable |
| `lib/whatsapp.js` | WhatsApp Cloud API: invio, lettura webhook, firma |
| `lib/meta-ads.js` | Meta Marketing API: metriche per annuncio, budget, pausa |
| `lib/lead-agents.js` | i 5 agenti: prompt e logica |
| `api/whatsapp.js` | webhook WhatsApp (verifica + messaggi in arrivo) |
| `api/agents.js` | API per il CRM + cron giornaliero |
| `index.html` | nuova sezione "📲 Macchina Lead" |

Dati in Redis:
- `wa:conv:<telefono>` — conversazione, scheda lead, annuncio di provenienza, stato (bot/umano/stop)
- `wa:index` — elenco conversazioni ordinate per ultima attivita
- `lead:proposals` — proposte di Media buyer e Creativo in attesa di approvazione
- `lead:report:last` — ultimo report dell'Analista

## Fasi

**Fase 1 — questo branch**
- webhook WhatsApp + Venditore + Qualificatore + passaggio a umano + STOP
- scrittura in PIPELINE + avviso Telegram per i lead caldi
- Analista (Meta + CRM), Media buyer con approvazione, Creativo con approvazione
- sezione CRM: conversazioni, lead, proposte, report, generatore creativita
- cron giornaliero (Analista → Media buyer → briefing su Telegram)

**Fase 2**
- appuntamenti su Google Calendar (slot liberi reali proposti dal Venditore)
- follow-up automatici con template WhatsApp approvati (fuori dalla finestra 24h)
- pubblicazione delle creativita approvate direttamente su Meta (upload immagine + ad)
- invio a Meta della Conversions API "lead qualificato" per far ottimizzare l'algoritmo sui lead buoni

**Fase 3 — rivenderlo**
- multi-cliente: la stessa macchina per i clienti di Creative Mess (un numero WhatsApp e un
  account pubblicitario per cliente). E un servizio vendibile a canone mensile.

## Setup (variabili d'ambiente su Vercel)

| Variabile | A cosa serve | Obbligatoria |
|---|---|---|
| `ANTHROPIC_API_KEY` | modello AI (gia presente) | si |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | memoria permanente (gia usata dai bot) | si, in produzione |
| `CRM_API_KEY` | chiave per le API del CRM (inventala lunga, poi inseriscila in ⚙️) | si |
| `WHATSAPP_TOKEN` | token permanente System User (Meta Business) | si |
| `WHATSAPP_PHONE_NUMBER_ID` | ID del numero WhatsApp Business | si |
| `WHATSAPP_VERIFY_TOKEN` | stringa a piacere, da ripetere in Meta al collegamento webhook | si |
| `META_APP_SECRET` | verifica firma webhook | consigliata |
| `META_ADS_TOKEN` | token con permesso `ads_read` (+ `ads_management` per eseguire) | per Analista/Media buyer |
| `META_AD_ACCOUNT_ID` | es. `act_1234567890` | per Analista/Media buyer |
| `META_ADS_WRITE` | `1` per far eseguire su Meta le proposte approvate | no (default: solo proposte) |
| `META_MAX_DAILY_BUDGET` | tetto giornaliero in euro per adset (default 50) | no |
| `AIRTABLE_TOKEN`, `AIRTABLE_BASE_ID` | scrittura lead in PIPELINE lato server | consigliata |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_ID` | avvisi lead caldi e briefing (bot gia esistente) | consigliata |
| `CRON_SECRET` | protegge il cron giornaliero di Vercel | consigliata |
| `PRIVACY_URL` | link informativa privacy citato dal bot | consigliata |

Collegamento WhatsApp (una volta sola):
1. Meta for Developers → app Business → prodotto WhatsApp → numero di telefono.
2. Webhook: URL `https://<dominio>/api/whatsapp`, token di verifica = `WHATSAPP_VERIFY_TOKEN`,
   iscriviti al campo `messages`.
3. In Gestione inserzioni crea campagne con obiettivo "Interazione" → destinazione "WhatsApp".
4. Controlla lo stato: `https://<dominio>/api/whatsapp` (mostra cosa e configurato).
