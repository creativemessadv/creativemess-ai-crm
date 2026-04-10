#!/usr/bin/env python3
"""
Delivery AI — genera contenuti per i clienti acquisiti.
Uso: python3 delivery.py --servizio social --cliente "Ristorante Rossi" --mese "Maggio 2026"
"""

import os, argparse
from datetime import datetime
from anthropic import Anthropic

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
client = Anthropic(api_key=ANTHROPIC_KEY)

# ── AGENTI ────────────────────────────────────────────────────────────────────

AGENTI = {

'social': {
'nome': 'Alessandro Colombo — Social Media Manager',
'prompt': """Sei Alessandro Colombo, Social Media Manager di Creative Mess ADV.
Crei piani editoriali mensili e copy per i clienti italiani.
Stile: diretto, coinvolgente, adatto al settore del cliente.
NON usare hashtag generici, sii specifico sul settore e sulla città.
Scrivi in italiano.""",
'task': lambda d: f"""Crea il piano editoriale per {d['mese']} per questo cliente:
Cliente: {d['cliente']}
Settore: {d['settore']}
Città: {d['citta']}
Canali: {d.get('canali', 'Instagram, Facebook')}
Obiettivo: {d.get('obiettivo', 'aumentare engagement e visibilità locale')}

Genera:
1. CALENDARIO (16 post: 4 a settimana)
   Per ogni post: Giorno, Tipo (Reel/Carosello/Foto/Story), Tema, Caption completa
2. 3 IDEE REEL con script breve
3. BIO AGGIORNATA per Instagram"""
},

'seo': {
'nome': 'Giulia Ferrara — SEO Specialist',
'prompt': """Sei Giulia Ferrara, SEO Specialist di Creative Mess ADV.
Crei strategie SEO e contenuti ottimizzati per PMI italiane.
Sei precisa, usi dati concreti, parli di volumi di ricerca realistici.
Scrivi in italiano.""",
'task': lambda d: f"""Crea la strategia SEO per questo cliente:
Cliente: {d['cliente']}
Settore: {d['settore']}
Città: {d['citta']}
Sito: {d.get('sito', 'da verificare')}

Genera:
1. TOP 10 KEYWORD TARGET (keyword + intento di ricerca + difficoltà stimata)
2. STRUTTURA SITO consigliata (pagine da creare/ottimizzare)
3. ARTICOLO BLOG COMPLETO ottimizzato per la keyword principale (min 600 parole)
4. META TITLE e META DESCRIPTION per le 5 pagine principali
5. SCHEDA GOOGLE BUSINESS: descrizione ottimizzata + 5 post consigliati"""
},

'adscopy': {
'nome': 'Fabio Martini — Ads Specialist',
'prompt': """Sei Fabio Martini, Ads Specialist di Creative Mess ADV.
Crei copy per Google Ads e Meta Ads per PMI italiane.
Sei diretto, orientato alla conversione, usi numeri e CTA forti.
Scrivi in italiano.""",
'task': lambda d: f"""Crea i copy pubblicitari per questo cliente:
Cliente: {d['cliente']}
Settore: {d['settore']}
Città: {d['citta']}
Budget mensile: {d.get('budget', 'da definire')}
Obiettivo: {d.get('obiettivo', 'lead generation')}

Genera:
GOOGLE ADS:
- 5 annunci responsivi (3 titoli + 2 descrizioni ciascuno, rispetta limiti caratteri)
- 10 keyword esatte da targetizzare
- 5 keyword negative

META ADS:
- 3 copy per carosello (headline + testo principale + CTA)
- 2 copy per video (hook 3 secondi + corpo + CTA)
- Targeting suggerito (interessi, età, geo)"""
},

'email_marketing': {
'nome': 'Irene Cattaneo — Email Marketing',
'prompt': """Sei Irene Cattaneo, Email Marketing Specialist di Creative Mess ADV.
Crei campagne email per PMI italiane con focus su aperture e conversioni.
Stile: professionale ma caldo, oggetti curiosi, CTA chiare.
Scrivi in italiano.""",
'task': lambda d: f"""Crea la campagna email per questo cliente:
Cliente: {d['cliente']}
Settore: {d['settore']}
Obiettivo campagna: {d.get('obiettivo', 'fidelizzazione clienti')}
Frequenza: {d.get('frequenza', '2 email al mese')}

Genera:
1. STRATEGIA (tipo di email, frequenza, segmentazione consigliata)
2. EMAIL 1 COMPLETA (oggetto + preheader + corpo HTML-ready)
3. EMAIL 2 COMPLETA (oggetto + preheader + corpo HTML-ready)
4. SEQUENZA BENVENUTO (3 email automatiche per nuovi iscritti)"""
},

'report_cliente': {
'nome': 'Riccardo Fontana — CEO',
'prompt': """Sei Riccardo Fontana, CEO di Creative Mess ADV.
Scrivi report mensili per i clienti in modo chiaro e professionale.
Mostra risultati concreti, spiega cosa è stato fatto, cosa si farà.
Se i numeri sono positivi: celebra e dai contesto.
Se sono negativi: sii onesto e dai il piano correttivo.
Scrivi in italiano, max 400 parole.""",
'task': lambda d: f"""Scrivi il report mensile per questo cliente:
Cliente: {d['cliente']}
Mese: {d['mese']}
Servizi attivi: {d.get('servizi', 'da specificare')}
Dati del mese: {d.get('dati', 'da inserire')}
Note: {d.get('note', '')}"""
},

'reputation': {
'nome': 'Davide Riva — Reputation Manager',
'prompt': """Sei Davide Riva, Reputation Manager di Creative Mess ADV.
Gestisci la reputazione online dei clienti italiani.
Rispondi alle recensioni in modo professionale, empatico e costruttivo.
Non essere mai aggressivo, trasforma i negativi in opportunità.
Scrivi in italiano.""",
'task': lambda d: f"""Scrivi le risposte alle recensioni per questo cliente:
Cliente: {d['cliente']}
Settore: {d['settore']}
Recensioni da gestire:
{d.get('recensioni', 'inserire testo recensioni')}

Per ogni recensione genera:
- Valutazione (positiva/negativa/neutra)
- Risposta professionale pronta da pubblicare
- Nota interna (cosa fare operativamente se negativa)"""
},

}

# ── MAIN ──────────────────────────────────────────────────────────────────────

def chiedi(domanda, default=''):
    r = input(f"{domanda}: ").strip()
    return r if r else default

def raccogli_dati(servizio):
    print(f"\n{'='*55}")
    print(f"  DELIVERY — {AGENTI[servizio]['nome']}")
    print(f"{'='*55}\n")

    dati = {
        'cliente': chiedi("Nome cliente"),
        'settore': chiedi("Settore"),
        'citta':   chiedi("Città"),
        'mese':    chiedi("Mese di riferimento", datetime.now().strftime('%B %Y')),
    }

    # Campi aggiuntivi per servizio specifico
    if servizio == 'social':
        dati['canali']   = chiedi("Canali (es. Instagram, Facebook, TikTok)", "Instagram, Facebook")
        dati['obiettivo'] = chiedi("Obiettivo", "aumentare engagement e visibilità locale")
    elif servizio == 'seo':
        dati['sito'] = chiedi("URL sito web", "")
    elif servizio == 'adscopy':
        dati['budget']   = chiedi("Budget mensile ads (es. €500)", "€500")
        dati['obiettivo'] = chiedi("Obiettivo campagna", "lead generation")
    elif servizio == 'email_marketing':
        dati['obiettivo']  = chiedi("Obiettivo campagna", "fidelizzazione clienti")
        dati['frequenza']  = chiedi("Frequenza invio", "2 email al mese")
    elif servizio == 'report_cliente':
        dati['servizi'] = chiedi("Servizi attivi")
        dati['dati']    = chiedi("Dati principali del mese (KPI, numeri)")
        dati['note']    = chiedi("Note aggiuntive", "")
    elif servizio == 'reputation':
        print("Incolla le recensioni da gestire (una per riga, premi Invio vuoto per finire):")
        righe = []
        while True:
            r = input("> ")
            if not r:
                break
            righe.append(r)
        dati['recensioni'] = '\n'.join(righe)

    return dati

if __name__ == '__main__':
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); exit(1)

    servizi_disponibili = list(AGENTI.keys())

    parser = argparse.ArgumentParser()
    parser.add_argument('--servizio', choices=servizi_disponibili,
                        help=f"Servizio: {', '.join(servizi_disponibili)}")
    args = parser.parse_args()

    if not args.servizio:
        print("\nServizi disponibili:")
        for i, s in enumerate(servizi_disponibili, 1):
            print(f"  {i}. {s} — {AGENTI[s]['nome']}")
        scelta = input("\nScegli numero: ").strip()
        try:
            args.servizio = servizi_disponibili[int(scelta) - 1]
        except (ValueError, IndexError):
            print("❌ Scelta non valida"); exit(1)

    agente = AGENTI[args.servizio]
    dati   = raccogli_dati(args.servizio)

    print(f"\n⏳ {agente['nome']} sta lavorando...")

    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=2000,
        system=agente['prompt'],
        messages=[{'role': 'user', 'content': agente['task'](dati)}]
    )
    testo = resp.content[0].text

    print(f"\n{'='*55}")
    print(f"  OUTPUT — pronto da usare")
    print(f"{'='*55}")
    print(testo)

    # Salva
    os.makedirs('data/delivery', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    nome_file = f"data/delivery/{args.servizio}_{dati['cliente'].replace(' ','_')}_{timestamp}.txt"
    with open(nome_file, 'w', encoding='utf-8') as f:
        f.write(testo)
    print(f"\n✅ Salvato: {nome_file}\n")
