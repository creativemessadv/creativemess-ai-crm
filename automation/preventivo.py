#!/usr/bin/env python3
"""
Generatore preventivi — Roberto inserisce i dati post-call,
Riccardo genera il testo pronto da incollare nel PDF.
Uso: python3 preventivo.py
"""

import os
from datetime import datetime
from anthropic import Anthropic

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
client = Anthropic(api_key=ANTHROPIC_KEY)

CATALOGO = """
SOCIAL MEDIA:
- Social Media Base: €400/mese (PMI locali)
- Social Media Pro: €700/mese (PMI strutturate)
- Social Media Premium: €1.200/mese (aziende medio-grandi)

SEO:
- SEO Local: €350/mese (attività locali)
- SEO Growth: €600/mese (PMI con e-commerce)
- SEO Enterprise: €1.200/mese (aziende strutturate)

ADVERTISING:
- Advertising Starter: €500/mese (PMI alle prime armi)
- Advertising Growth: €900/mese (PMI strutturate)
- Advertising Performance: €1.500/mese (aziende con obiettivi chiari)

WEB:
- Sito Vetrina: da €2.500 (una tantum, attività locali)
- Sito Professionale: da €4.500 (una tantum, PMI strutturate)
- E-Commerce: da €7.500 (una tantum, vendita online)
- Manutenzione Web: €150/mese (tutti i clienti con sito CM)

PACCHETTI:
- Digital Start: €1.200/mese (PMI che iniziano)
- Digital Growth: €2.000/mese (PMI in crescita)
- Digital Premium: €3.200/mese (PMI strutturate)
- Full Digital Partner: €5.000/mese (aziende che vogliono un partner)

EMAIL MARKETING:
- Email Marketing Base: €300/mese (PMI senza database)
- Email Marketing Pro: €600/mese (e-commerce e PMI strutturate)

REPUTATION MANAGEMENT: €400/mese (ristoranti, hotel, retail)

CRO Base: €500/mese (siti con traffico esistente)

CONSULENZA:
- Consulenza Strategica: €200/ora (min 2h per sessione)
- Fractional CMO: €2.500/mese (PMI senza marketing interno, min 6 mesi)

AI & AUTOMAZIONE:
- AI Automation Base: da €800 (una tantum, PMI che vogliono automatizzare)
- AI Automation Pro: da €2.000 (una tantum, aziende strutturate)

E-COMMERCE:
- E-Commerce Management: €800/mese (shop online attivi)
- E-Commerce Growth: €1.500/mese (e-commerce in crescita)
"""

RICCARDO_PREVENTIVO = f"""Sei Riccardo Fontana, CEO di Creative Mess ADV, web agency italiana 100% AI-powered.
Scrivi il testo di un preventivo professionale per un potenziale cliente.

CATALOGO SERVIZI E PREZZI:
{CATALOGO}

ISTRUZIONI:
- Scrivi in italiano, tono professionale e diretto
- Struttura il testo in sezioni chiare pronte da incollare in un PDF
- Personalizza ogni sezione sul settore e sulla situazione specifica del cliente
- Per i servizi una tantum (siti web, AI automation) indica il prezzo esatto o la fascia
- Per i servizi mensili indica il totale mensile ricorrente
- Includi sempre il ROI atteso o il beneficio concreto per quel tipo di azienda
- Sii specifico: non scrivere "miglioreremo la vostra presenza online", scrivi "porteremo il vostro ristorante in prima pagina su Google Maps per 'ristorante Milano'"
- Non usare asterischi o markdown, solo testo pulito con titoli in MAIUSCOLO

STRUTTURA DA SEGUIRE:
1. SINTESI DELLA SITUAZIONE ATTUALE (2-3 righe su cosa manca oggi)
2. LA NOSTRA PROPOSTA (servizi selezionati con motivazione)
3. INVESTIMENTO (prezzi chiari, distingui una tantum da mensile)
4. COSA OTTIENI (risultati concreti attesi nei primi 3-6 mesi)
5. PERCHÉ CREATIVE MESS ADV (2-3 righe differenzianti, focus AI-powered)
6. PROSSIMI PASSI (cosa fare per iniziare)"""


def chiedi(domanda, default=''):
    risposta = input(f"{domanda}: ").strip()
    return risposta if risposta else default


def raccogli_dati():
    print("\n" + "="*55)
    print("  GENERATORE PREVENTIVO — Creative Mess ADV")
    print("="*55)
    print("Inserisci i dati raccolti durante la call:\n")

    dati = {
        'nome_azienda':    chiedi("Nome azienda"),
        'settore':         chiedi("Settore (es. ristorante, studio dentistico)"),
        'citta':           chiedi("Città"),
        'referente':       chiedi("Nome referente"),
        'situazione':      chiedi("Situazione attuale (sito vecchio? zero social? zero ads?)"),
        'obiettivo':       chiedi("Obiettivo principale (più clienti? più prenotazioni? vendite online?)"),
        'servizi':         chiedi("Servizi di interesse (es. Social Pro + SEO Local + Sito Vetrina)"),
        'budget':          chiedi("Budget indicativo (es. €1.000/mese, non so, alto)", default='da definire'),
        'note':            chiedi("Note aggiuntive dalla call (opzionale)", default=''),
    }
    return dati


def genera_preventivo(dati):
    contesto = f"""Cliente: {dati['nome_azienda']}
Settore: {dati['settore']}
Città: {dati['citta']}
Referente: {dati['referente']}

Situazione attuale: {dati['situazione']}
Obiettivo principale: {dati['obiettivo']}
Servizi di interesse: {dati['servizi']}
Budget indicativo: {dati['budget']}
Note dalla call: {dati['note']}

Data preventivo: {datetime.now().strftime('%d/%m/%Y')}"""

    print("\n⏳ Riccardo sta preparando il preventivo...")

    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=1500,
        system=RICCARDO_PREVENTIVO,
        messages=[{'role': 'user', 'content':
            f'Genera il testo del preventivo per questo cliente:\n\n{contesto}'}]
    )
    return resp.content[0].text


def salva_preventivo(testo, nome_azienda):
    os.makedirs('data/preventivi', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    nome_file = nome_azienda.lower().replace(' ', '_').replace('/', '_')
    path = f"data/preventivi/{nome_file}_{timestamp}.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(testo)
    return path


if __name__ == '__main__':
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante")
        exit(1)

    dati = raccogli_dati()

    if not dati['nome_azienda']:
        print("❌ Nome azienda obbligatorio")
        exit(1)

    testo = genera_preventivo(dati)

    print("\n" + "="*55)
    print("  TESTO PREVENTIVO — pronto per il PDF")
    print("="*55)
    print(testo)

    path = salva_preventivo(testo, dati['nome_azienda'])
    print(f"\n{'='*55}")
    print(f"✅ Salvato in: {path}")
    print(f"{'='*55}\n")
