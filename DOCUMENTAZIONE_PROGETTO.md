# Creative Mess ADV — Sistema AI Operativo
## Documentazione Completa del Progetto

---

# 1. OBIETTIVO

Costruire un clone AI di Creative Mess ADV capace di:
- Trovare potenziali clienti in automatico ogni giorno
- Contattarli con email personalizzate via Chiara (AI)
- Gestire i report operativi via Riccardo (AI CEO)
- Generare preventivi e contenuti per i clienti acquisiti
- Obiettivo economico: €400.000 in 9 mesi

Roberto Salvatori (Presidente) si occupa solo di:
- 20 call di vendita a settimana
- Decisioni strategiche
- Caricare il CSV su Instantly ogni lunedì (5 minuti)

---

# 2. INFRASTRUTTURA TECNICA

## Server VPS
- **Provider:** Hetzner Cloud
- **IP:** 178.104.151.95
- **OS:** Ubuntu 24.04 LTS
- **Path progetto:** /root/agency/automation
- **Process manager:** PM2 (Node.js)
- **Accesso:** ssh root@178.104.151.95

## Repository GitHub
- **URL:** github.com/creativemessadv/creativemess-ai-crm
- **Branch:** claude/web-agency-services-5CZoX

## Dominio Email
- **Dominio:** creativemessadv.it
- **Provider:** Zoho Mail (smtppro.zoho.eu)
- **Account attivi:** 12 account AI agents + r.salvatori (personale)

---

# 3. SERVIZI ESTERNI ATTIVATI

| Servizio | Piano | Costo | Uso |
|----------|-------|-------|-----|
| Anthropic Claude | API pay-per-use | ~€50-100/mese | Generazione email, report, preventivi, contenuti |
| Apify | Starter $29/mese | $29/mese | Scraping Google Maps per trovare prospect |
| Instantly.ai | Growth $47/mese | $47/mese | Invio cold email, warmup account, follow-up automatici |
| Brevo | Free tier | €0 | Invio email interne (report Riccardo→Roberto) |
| Hetzner VPS | CX21 | ~€5/mese | Server H24 per automation |
| GitHub | Free | €0 | Repository codice |

**Totale costi fissi mensili: ~€130-180/mese**

---

# 4. AGENTI AI

## Chiara Benedetti (c.benedetti@creativemessadv.it)
**Ruolo:** Outreach Specialist
**Cosa fa:** Scrive email cold personalizzate per acquisire clienti italiani
**Come:** Analizza settore, città e sito dell'azienda target → genera email con oggetto max 7 parole + corpo max 100 parole + CTA call 15 minuti + follow-up dopo 3 giorni
**Quando:** Ogni giorno alle 08:00 (automatico via PM2)

## Riccardo Fontana (r.fontana@creativemessadv.it)
**Ruolo:** CEO — Report operativi
**Cosa fa:** Analizza l'attività giornaliera del sistema e manda report a Roberto
**Come:** Legge stato PM2, statistiche outreach, errori → genera report con Claude → manda via Brevo
**Quando:**
- Ogni giorno alle 13:00 (report mattina)
- Ogni giorno alle 19:00 (report sera)
- Ogni lunedì alle 07:00 (briefing strategico settimanale)

## Alessandro Colombo (a.colombo@creativemessadv.it)
**Ruolo:** Social Media Manager
**Cosa fa:** Genera piani editoriali mensili e copy per Instagram/Facebook/TikTok
**Come:** Roberto inserisce dati cliente → Claude genera calendario 16 post + 3 idee Reel + bio aggiornata
**Uso:** Manuale via `python3 delivery.py --servizio social`

## Giulia Ferrara (g.ferrara@creativemessadv.it)
**Ruolo:** SEO Specialist
**Cosa fa:** Crea strategie SEO e contenuti ottimizzati
**Come:** Roberto inserisce dati cliente → Claude genera top 10 keyword + struttura sito + articolo blog 600 parole + meta tag + scheda Google Business
**Uso:** Manuale via `python3 delivery.py --servizio seo`

## Fabio Martini (f.martini@creativemessadv.it)
**Ruolo:** Ads Specialist
**Cosa fa:** Crea copy per Google Ads e Meta Ads
**Come:** Roberto inserisce dati cliente → Claude genera 5 annunci Google (titoli + descrizioni) + 10 keyword + copy Meta Ads + targeting suggerito
**Uso:** Manuale via `python3 delivery.py --servizio adscopy`

## Irene Cattaneo (i.cattaneo@creativemessadv.it)
**Ruolo:** Email Marketing Specialist
**Cosa fa:** Crea campagne email e sequenze automatiche
**Come:** Roberto inserisce dati cliente → Claude genera strategia + 2 email complete + sequenza benvenuto 3 step
**Uso:** Manuale via `python3 delivery.py --servizio email_marketing`

## Davide Riva (d.riva@creativemessadv.it)
**Ruolo:** Reputation Manager
**Cosa fa:** Gestisce recensioni online (Google, TripAdvisor, ecc.)
**Come:** Roberto incolla le recensioni → Claude genera risposte professionali pronte da pubblicare + note interne
**Uso:** Manuale via `python3 delivery.py --servizio reputation`

## Agenti email rimanenti (non ancora assegnati a script specifici)
- f.neri@creativemessadv.it
- s.valenti@creativemessadv.it
- a.tornatore@creativemessadv.it
- e.respighi@creativemessadv.it
- info@creativemessadv.it

---

# 5. PIPELINE AUTOMATICA GIORNALIERA

```
07:00 — Scraper (PM2: scraper-daily)
        Apify Google Maps → trova 100 aziende nel settore/città del giorno
        Crawla siti web per trovare email mancanti
        Salva in data/prospect_*.json

08:00 — Outreach (PM2: outreach-daily)
        Legge prospect nuovi da data/prospect_*.json
        Chiara genera 100 email personalizzate via Claude API
        Salva CSV in data/outreach/batch_YYYYMMDD_HHMM.csv
        Aggiorna data/sent.json (log email generate)

13:00 — Report mattina (PM2: report-mattina)
        Riccardo legge statistiche + stato PM2 + errori
        Genera report via Claude
        Manda email a r.salvatori@creativemessadv.it via Brevo

19:00 — Report sera (PM2: report-sera)
        Stesso del report mattina, periodo pomeriggio

Lunedì 07:00 — Briefing settimanale (PM2: briefing-settimanale)
        Riccardo analizza settimana + stats Instantly + performance
        Genera briefing strategico con raccomandazioni target settimana dopo
        Manda email a Roberto
```

## Ogni lunedì (Roberto, 5 minuti — manuale)
```
1. Scarica CSV dal VPS:
   scp root@178.104.151.95:/root/agency/automation/data/outreach/batch_*.csv ~/Desktop/

2. Vai su Instantly → campagna → Leads → Add Leads → Upload CSV

3. Mappa campi: email, first_name, last_name, company_name, city,
   website, subject, body, followup_subject, followup_body

4. Import → conferma
```

---

# 6. SISTEMA TARGETS (Scraper Automatico)

Il file `data/targets.json` contiene 66 combinazioni settore/città in Lombardia.
Lo scraper ruota automaticamente: ogni giorno attacca un settore diverso.

**Città coperte:** Milano, Bergamo, Brescia, Monza, Como, Varese, Pavia, Cremona, Mantova, Lecco, Lodi, Sondrio

**Settori coperti:**
- Food & Beverage: ristoranti, pizzerie, bar, pasticcerie, gelaterie, enoteche, catering, food truck
- Salute: dentisti, medici estetici, fisioterapisti, nutrizionisti, psicologi, veterinari, farmacie
- Bellezza & Fitness: palestre, centri benessere, parrucchieri, centri estetici, barbieri, nail salon, scuole di danza
- Ospitalità: hotel, B&B
- Retail: abbigliamento, gioiellerie, ottica, arredamento, fiorai
- Automotive: concessionarie, officine, carrozzerie, noleggio auto
- Formazione: corsi di lingua, scuole di danza
- Edilizia: imprese edili, interior design

---

# 7. FILE PRINCIPALI

| File | Descrizione |
|------|-------------|
| `automation/scraper.py` | Scraper Google Maps via Apify |
| `automation/outreach.py` | Generatore email Chiara → CSV |
| `automation/report.py` | Report giornalieri/settimanali Riccardo |
| `automation/preventivo.py` | Generatore testo preventivi post-call |
| `automation/delivery.py` | 6 agenti delivery (social, SEO, ads, email, report, reputation) |
| `automation/ecosystem.config.js` | Configurazione PM2 (5 processi schedulati) |
| `automation/run_outreach.sh` | Script lancio outreach |
| `automation/run_scraper.sh` | Script lancio scraper (--auto --n 100) |
| `automation/run_report_mattina.sh` | Script report 13:00 |
| `automation/run_report_sera.sh` | Script report 19:00 |
| `automation/run_report_weekly.sh` | Script briefing lunedì |
| `data/targets.json` | Lista target settore/città con indice rotazione |
| `data/sent.json` | Log prospect già processati (evita duplicati) |
| `data/outreach/` | CSV generati da caricare su Instantly |
| `data/preventivi/` | Testi preventivi generati |
| `data/delivery/` | Output agenti delivery |

---

# 8. COMANDI UTILI VPS

```bash
# Accesso VPS
ssh root@178.104.151.95

# Stato processi
pm2 list
pm2 logs

# Lanciare manualmente
cd /root/agency/automation
set -a; source .env; set +a

python3 scraper.py --settore "dentisti" --citta "Milano" --n 100
python3 outreach.py
python3 report.py mattina
python3 report.py pomeriggio
python3 report.py weekly
python3 preventivo.py
python3 delivery.py

# Aggiornare codice dal GitHub
git pull origin claude/web-agency-services-5CZoX

# Ricaricare PM2
pm2 delete all && pm2 start ecosystem.config.js && pm2 save
```

---

# 9. CATALOGO SERVIZI E PREZZI

**SOCIAL MEDIA**
- Social Media Base: €400/mese (PMI locali)
- Social Media Pro: €700/mese (PMI strutturate)
- Social Media Premium: €1.200/mese (aziende medio-grandi)

**SEO**
- SEO Local: €350/mese
- SEO Growth: €600/mese
- SEO Enterprise: €1.200/mese

**ADVERTISING**
- Advertising Starter: €500/mese
- Advertising Growth: €900/mese
- Advertising Performance: €1.500/mese

**WEB**
- Sito Vetrina: da €2.500 (una tantum)
- Sito Professionale: da €4.500 (una tantum)
- E-Commerce: da €7.500 (una tantum)
- Manutenzione Web: €150/mese

**PACCHETTI**
- Digital Start: €1.200/mese
- Digital Growth: €2.000/mese
- Digital Premium: €3.200/mese
- Full Digital Partner: €5.000/mese

**EMAIL MARKETING**
- Email Marketing Base: €300/mese
- Email Marketing Pro: €600/mese

**ALTRI**
- Reputation Management: €400/mese
- CRO Base: €500/mese
- Consulenza Strategica: €200/ora
- Fractional CMO: €2.500/mese
- AI Automation Base: da €800 (una tantum)
- AI Automation Pro: da €2.000 (una tantum)
- E-Commerce Management: €800/mese
- E-Commerce Growth: €1.500/mese

---

# 10. MATEMATICA OBIETTIVO €400K

| Metrica | Valore |
|---------|--------|
| Email generate al giorno | 100 |
| Email a settimana | 500 |
| Tasso risposta atteso | 2-3% |
| Risposte/settimana | 10-15 |
| Call Roberto/settimana | 20 max |
| Tasso chiusura call | 20-25% |
| Nuovi clienti/settimana | 3-5 |
| Ticket medio mensile | €1.200 (Digital Start) |
| Revenue mensile a regime (50 clienti) | €60.000 |
| Obiettivo 9 mesi | €400.000 |

---

# 11. COSA MANCA / ROADMAP

**Da completare:**
- [ ] SPF/DKIM/DMARC su Zoho (deliverability email)
- [ ] Espandere a altre regioni italiane (dopo Lombardia)
- [ ] Agente per creazione siti (Webflow/WordPress)
- [ ] Integrazione CRM per gestione clienti acquisiti
- [ ] Dashboard web per Roberto (visualizzare stats in tempo reale)
- [ ] Aumentare DAILY_LIMIT a 100 dopo 2 settimane di warmup

**Stato warmup account:**
Gli account Zoho sono stati connessi il 14/04/2026. Attendere 2-3 settimane per reputazione ottimale prima di alzare i volumi.

---

*Documento generato il 14/04/2026 — Creative Mess ADV Sistema AI*
