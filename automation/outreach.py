#!/usr/bin/env python3
"""
Pipeline outreach automatica — Claude genera email → Instantly.ai manda
Gira ogni giorno via PM2. Legge prospect da JSON, aggiunge lead alla campagna.
Follow-up gestiti automaticamente da Instantly tramite sequenza campagna.
"""

import os, json, time, random, requests
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY   = os.getenv('ANTHROPIC_API_KEY', '')
INSTANTLY_KEY   = os.getenv('INSTANTLY_API_KEY', '')
DAILY_LIMIT     = int(os.getenv('DAILY_LIMIT', '30'))
CAMPAIGN_NAME   = os.getenv('INSTANTLY_CAMPAIGN', 'Creative Mess — Outreach Italia')
DATA_DIR        = Path('data')
SENT_LOG        = DATA_DIR / 'sent.json'
INSTANTLY_BASE  = 'https://api.instantly.ai/api/v2'

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

# ── INSTANTLY HELPERS ─────────────────────────────────────────────────────────

def instantly_headers():
    return {
        'Authorization': f'Bearer {INSTANTLY_KEY}',
        'Content-Type': 'application/json'
    }

def get_or_create_campaign():
    """Trova o crea la campagna su Instantly"""
    # Cerca campagna esistente
    try:
        r = requests.get(
            f'{INSTANTLY_BASE}/campaigns',
            params={'limit': 50},
            headers=instantly_headers(),
            timeout=15
        )
        if r.status_code == 200:
            for c in r.json().get('items', []):
                if c.get('name') == CAMPAIGN_NAME:
                    print(f"   Campagna trovata: {c['id']}")
                    return c['id']
    except Exception as e:
        print(f"   ⚠️  Errore ricerca campagna: {e}")

    # Crea nuova campagna con sequenza 3 step
    payload = {
        'name': CAMPAIGN_NAME,
        'campaign_schedule': {
            'schedules': [{
                'name': 'Italia Orario Lavorativo',
                'timing': {'from': '08:00', 'to': '18:00'},
                'days': {
                    '0': True, '1': True, '2': True,
                    '3': True, '4': True, '5': False, '6': False
                },
                'timezone': 'UTC'
            }]
        },
        'sequences': [{
            'steps': [
                {
                    'type': 'email',
                    'delay': 0,
                    'variants': [{
                        'subject': '{{subject}}',
                        'body':    '{{body}}'
                    }]
                },
                {
                    'type': 'email',
                    'delay': 3,   # follow-up dopo 3 giorni
                    'variants': [{
                        'subject': '{{followup_subject}}',
                        'body':    '{{followup_body}}'
                    }]
                }
            ]
        }],
        'email_gap': 5,    # minuti tra un invio e l'altro
        'daily_limit': 50  # Instantly gestisce il warming
    }

    try:
        r = requests.post(
            f'{INSTANTLY_BASE}/campaigns',
            json=payload,
            headers=instantly_headers(),
            timeout=15
        )
        if r.status_code in (200, 201):
            campaign_id = r.json().get('id') or r.json().get('campaign_id', '')
            print(f"   ✅ Campagna creata: {campaign_id}")
            return campaign_id
        else:
            print(f"   ❌ Errore creazione campagna: {r.status_code} {r.text[:200]}")
            return ''
    except Exception as e:
        print(f"   ❌ Errore creazione campagna: {e}")
        return ''

def add_lead_to_campaign(campaign_id, email, nome, subject, body, fu_subject, fu_body):
    """Aggiunge un lead alla campagna Instantly"""
    first_name = nome.split()[0] if nome else ''
    last_name  = ' '.join(nome.split()[1:]) if len(nome.split()) > 1 else ''

    payload = {
        'campaign_id': campaign_id,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'custom_variables': {
            'subject':         subject,
            'body':            body.replace('\n', '<br>'),
            'followup_subject': fu_subject,
            'followup_body':   fu_body.replace('\n', '<br>')
        }
    }

    try:
        r = requests.post(
            f'{INSTANTLY_BASE}/leads',
            json=payload,
            headers=instantly_headers(),
            timeout=15
        )
        return r.status_code in (200, 201)
    except Exception as e:
        print(f"   ❌ Errore add lead: {e}")
        return False

# ── EMAIL GENERATION ──────────────────────────────────────────────────────────

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

def run_outreach():
    print(f"\n{'='*55}")
    print(f"🚀 Outreach automatico — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*55}")

    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); return
    if not INSTANTLY_KEY:
        print("❌ INSTANTLY_API_KEY mancante"); return

    sent      = load_sent()
    prospects = load_prospects()

    # Solo prospect con email non ancora contattati
    to_contact = [
        p for p in prospects
        if p.get('email') and p['email'] not in sent
    ]

    print(f"📋 Prospect disponibili: {len(to_contact)}")
    print(f"📤 Limite giornaliero: {DAILY_LIMIT}")

    if not to_contact:
        print("⚠️  Nessun nuovo prospect — lancia run_scraper.sh")
        return

    print(f"\n🎯 Recupero campagna Instantly...")
    campaign_id = get_or_create_campaign()
    if not campaign_id:
        print("❌ Impossibile ottenere campagna — abort"); return

    added, errors = 0, 0

    for p in to_contact[:DAILY_LIMIT]:
        nome    = p.get('nome', 'Azienda')
        email   = p['email']
        settore = p.get('settore', '')
        citta   = p.get('citta', '')
        sito    = p.get('sito', '')

        print(f"\n📧 {nome} ({email})")

        try:
            # Genera email principale
            print(f"   ✍️  Chiara genera email...")
            raw = generate_email(nome, settore, citta, sito)
            subj, body = parse_email(raw)
            if not subj or not body:
                print(f"   ⚠️  Email non valida, skip")
                errors += 1
                continue

            # Genera follow-up
            fu_raw = generate_followup(nome, settore, subj)
            fu_subj, fu_body = parse_email(fu_raw)
            if not fu_subj:
                fu_subj = f"Re: {subj}"
                fu_body = fu_raw

            print(f"   📌 Oggetto: {subj}")

            # Aggiungi a Instantly
            ok = add_lead_to_campaign(campaign_id, email, nome, subj, body, fu_subj, fu_body)

            if ok:
                sent[email] = {
                    'nome': nome,
                    'settore': settore,
                    'citta': citta,
                    'oggetto': subj,
                    'added_at': datetime.now().isoformat(),
                    'status': 'queued',
                    'platform': 'instantly'
                }
                added += 1
                print(f"   ✅ Aggiunto a Instantly!")
            else:
                errors += 1

        except Exception as e:
            print(f"   ❌ Errore: {e}")
            errors += 1
            continue

        time.sleep(random.uniform(3, 8))  # rispetta rate limit Claude API

    save_sent(sent)

    print(f"\n{'='*55}")
    print(f"✅ Lead aggiunti oggi: {added}")
    print(f"❌ Errori: {errors}")
    print(f"📊 Totale in pipeline: {len(sent)}")
    print(f"{'='*55}\n")

if __name__ == '__main__':
    run_outreach()
