#!/usr/bin/env python3
"""
Pipeline outreach — Claude genera email personalizzate → salva CSV pronto per Instantly
Gira ogni giorno via PM2. Legge prospect da JSON, genera email, esporta CSV.
L'utente carica il CSV su Instantly una volta a settimana (Add Leads → Upload CSV).
"""

import os, json, time, random, csv
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY  = os.getenv('ANTHROPIC_API_KEY', '')
DAILY_LIMIT    = int(os.getenv('DAILY_LIMIT', '50'))
DATA_DIR       = Path('data')
SENT_LOG       = DATA_DIR / 'sent.json'
OUTREACH_DIR   = DATA_DIR / 'outreach'

client = Anthropic(api_key=ANTHROPIC_KEY)

CHIARA_PROMPT = """Sei Chiara Benedetti, specialista outreach di Creative Mess ADV, web agency italiana 100% AI-powered.
Scrivi email cold brevi e personalizzate per acquisire clienti italiani.
Servizi: siti web, SEO, Google Ads, Meta Ads, social media, e-commerce.

Regole FONDAMENTALI:
- Oggetto: max 7 parole, curioso o specifico sul settore
- Corpo: max 100 parole, tono diretto e professionale
- Personalizza sempre sul tipo di attività
- CTA unica: proponi una call di 15 minuti
- NON usare: "spero questa email ti trovi bene", "mi permetto di contattarla"
- Firma: Chiara Benedetti, Creative Mess ADV

Rispondi SOLO con questo formato esatto:
OGGETTO: [oggetto]
---
[corpo email completo con firma]"""

FOLLOWUP_PROMPT = """Sei Chiara Benedetti di Creative Mess ADV.
Scrivi un follow-up (max 60 parole) a una cold email inviata 3 giorni fa.
Tono: naturale, non insistente. Aggiungi un insight sul settore come gancio.
Firma: Chiara Benedetti, Creative Mess ADV

Formato:
OGGETTO: [oggetto follow-up breve]
---
[testo follow-up]"""

# ── HELPERS ───────────────────────────────────────────────────────────────────

def load_sent():
    if SENT_LOG.exists():
        return json.loads(SENT_LOG.read_text())
    return {}

def save_sent(sent):
    DATA_DIR.mkdir(exist_ok=True)
    SENT_LOG.write_text(json.dumps(sent, ensure_ascii=False, indent=2))

def load_prospects():
    prospects = []
    for f in DATA_DIR.glob('prospect_*.json'):
        try:
            prospects.extend(json.loads(f.read_text()))
        except Exception:
            pass
    return prospects

def generate_email(nome, settore, citta, sito=''):
    context = f"Azienda: {nome}\nSettore: {settore}\nCittà: {citta}"
    if sito:
        context += f"\nSito: {sito}"
    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=400,
        system=CHIARA_PROMPT,
        messages=[{'role': 'user', 'content': context}]
    )
    return resp.content[0].text

def generate_followup(nome, settore, oggetto_orig):
    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=300,
        system=FOLLOWUP_PROMPT,
        messages=[{'role': 'user', 'content':
            f"Settore: {settore}\nNome azienda: {nome}\nOggetto email precedente: {oggetto_orig}"}]
    )
    return resp.content[0].text

def parse_email(text):
    lines = text.strip().split('\n')
    oggetto, corpo_lines, after = '', [], False
    for line in lines:
        if line.startswith('OGGETTO:'):
            oggetto = line.replace('OGGETTO:', '').strip()
        elif line.strip() == '---':
            after = True
        elif after:
            corpo_lines.append(line)
    return oggetto, '\n'.join(corpo_lines).strip()

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run_outreach():
    print(f"\n{'='*55}")
    print(f"✍️  Generazione email — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*55}")

    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); return

    sent      = load_sent()
    prospects = load_prospects()

    to_contact = [
        p for p in prospects
        if p.get('email') and p['email'] not in sent
    ]

    print(f"📋 Prospect disponibili: {len(to_contact)}")
    print(f"📤 Da processare oggi: {min(DAILY_LIMIT, len(to_contact))}")

    if not to_contact:
        print("⚠️  Nessun nuovo prospect — lancia run_scraper.sh")
        return

    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
    timestamp  = datetime.now().strftime('%Y%m%d_%H%M')
    csv_path   = OUTREACH_DIR / f'batch_{timestamp}.csv'

    rows       = []
    processed  = 0
    errors     = 0

    for p in to_contact[:DAILY_LIMIT]:
        nome    = p.get('nome', 'Azienda')
        email   = p['email']
        settore = p.get('settore', '')
        citta   = p.get('citta', '')
        sito    = p.get('sito', '')

        print(f"\n📧 {nome} ({email})")

        try:
            print(f"   ✍️  Chiara genera email...")
            raw = generate_email(nome, settore, citta, sito)
            subj, body = parse_email(raw)
            if not subj or not body:
                print(f"   ⚠️  Email non valida, skip")
                errors += 1
                continue

            fu_raw = generate_followup(nome, settore, subj)
            fu_subj, fu_body = parse_email(fu_raw)
            if not fu_subj:
                fu_subj = f"Re: {subj}"
                fu_body = fu_raw

            print(f"   📌 {subj}")

            rows.append({
                'email':            email,
                'first_name':       nome.split()[0] if nome else '',
                'last_name':        ' '.join(nome.split()[1:]) if len(nome.split()) > 1 else '',
                'company_name':     nome,
                'city':             citta,
                'website':          sito,
                'subject':          subj,
                'body':             body,
                'followup_subject': fu_subj,
                'followup_body':    fu_body,
            })

            sent[email] = {
                'nome': nome, 'settore': settore, 'citta': citta,
                'oggetto': subj,
                'generated_at': datetime.now().isoformat(),
                'status': 'ready_to_upload',
                'csv': str(csv_path)
            }
            processed += 1
            print(f"   ✅ Pronto!")

        except Exception as e:
            print(f"   ❌ {e}")
            errors += 1
            continue

        time.sleep(random.uniform(2, 5))

    # Salva CSV per Instantly
    if rows:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n📊 CSV salvato: {csv_path}")
        print(f"   → Carica su Instantly: Campaigns → Add Leads → Upload CSV")

    save_sent(sent)

    print(f"\n{'='*55}")
    print(f"✅ Email generate: {processed}")
    print(f"❌ Errori: {errors}")
    print(f"📊 Totale processati: {len(sent)}")
    print(f"{'='*55}\n")

if __name__ == '__main__':
    run_outreach()
