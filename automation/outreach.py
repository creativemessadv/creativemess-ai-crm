#!/usr/bin/env python3
"""
Pipeline outreach automatica — Claude genera email → Brevo manda
Gira ogni giorno via PM2. Legge prospect da JSON, manda email personalizzate.
"""

import os, json, time, random, requests, re
from datetime import datetime, timedelta
from pathlib import Path
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
BREVO_KEY     = os.getenv('BREVO_API_KEY', '')
FROM_EMAIL    = os.getenv('FROM_EMAIL', 'chiara@creativemessadv.com')
FROM_NAME     = os.getenv('FROM_NAME', 'Chiara Benedetti — Creative Mess ADV')
DAILY_LIMIT   = int(os.getenv('DAILY_LIMIT', '20'))  # aumenta gradualmente
DATA_DIR      = Path('data')
SENT_LOG      = DATA_DIR / 'sent.json'

client = Anthropic(api_key=ANTHROPIC_KEY)

CHIARA_PROMPT = """Sei Chiara Benedetti, specialista outreach di Creative Mess ADV, web agency italiana.
Scrivi email cold brevi e personalizzate per acquisire clienti italiani per questi servizi:
siti web, SEO, Google Ads, Meta Ads, social media, email marketing, e-commerce.
Regole FONDAMENTALI:
- Oggetto: max 7 parole, curioso o specifico sul settore
- Corpo: max 100 parole
- Tono: professionale ma diretto, non da venditore
- Personalizza sempre sul settore dell'azienda
- CTA unica: proponi una chiamata di 15 minuti
- NON usare: "spero questa email ti trovi bene", "mi permetto di contattarla", ecc.
- Firma: Chiara Benedetti, Creative Mess ADV
Rispondi SOLO con il testo email nel formato:
OGGETTO: [oggetto]
---
[corpo email]"""

def load_sent():
    if SENT_LOG.exists():
        return json.loads(SENT_LOG.read_text())
    return {}

def save_sent(sent):
    DATA_DIR.mkdir(exist_ok=True)
    SENT_LOG.write_text(json.dumps(sent, ensure_ascii=False, indent=2))

def load_prospects():
    """Carica tutti i prospect dai file JSON in data/"""
    prospects = []
    for f in DATA_DIR.glob('prospect_*.json'):
        try:
            data = json.loads(f.read_text())
            prospects.extend(data)
        except:
            pass
    return prospects

def generate_email(nome, settore, citta, sito=''):
    """Chiara genera email personalizzata"""
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

def parse_email(text):
    """Estrae oggetto e corpo dall'output di Chiara"""
    lines = text.strip().split('\n')
    oggetto = ''
    corpo_lines = []
    after_sep = False
    
    for line in lines:
        if line.startswith('OGGETTO:'):
            oggetto = line.replace('OGGETTO:', '').strip()
        elif line.strip() == '---':
            after_sep = True
        elif after_sep:
            corpo_lines.append(line)
    
    corpo = '\n'.join(corpo_lines).strip()
    return oggetto, corpo

def send_brevo(to_email, to_name, oggetto, corpo_text):
    """Manda email via Brevo API"""
    corpo_html = corpo_text.replace('\n', '<br>')
    
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": oggetto,
        "htmlContent": f"""<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#333;max-width:600px">
{corpo_html}
</div>""",
        "textContent": corpo_text,
        "headers": {"X-Mailer": "CreativeMess-AI"}
    }
    
    r = requests.post(
        'https://api.brevo.com/v3/smtp/email',
        json=payload,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'},
        timeout=15
    )
    return r.status_code in (200, 201), r.text

def run_outreach():
    print(f"\n{'='*50}")
    print(f"🚀 Outreach automatico — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*50}")
    
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); return
    if not BREVO_KEY:
        print("❌ BREVO_API_KEY mancante"); return
    
    sent = load_sent()
    prospects = load_prospects()
    
    # Filtra: solo con email, non già contattati
    to_contact = [
        p for p in prospects 
        if p.get('email') and p['email'] not in sent
    ]
    
    print(f"📋 Prospect disponibili: {len(to_contact)}")
    print(f"📤 Limite giornaliero: {DAILY_LIMIT}")
    
    if not to_contact:
        print("⚠️  Nessun nuovo prospect — lancia scraper.py per trovarne altri")
        return
    
    sent_today = 0
    errors = 0
    
    for p in to_contact[:DAILY_LIMIT]:
        try:
            nome = p.get('nome', 'Azienda')
            email = p['email']
            settore = p.get('settore', '')
            citta = p.get('citta', '')
            sito = p.get('sito', '')
            
            print(f"\n📧 {nome} ({email})")
            
            # Genera email con Chiara
            print(f"   ✍️  Chiara genera email...")
            raw = generate_email(nome, settore, citta, sito)
            oggetto, corpo = parse_email(raw)
            
            if not oggetto or not corpo:
                print(f"   ⚠️  Email non valida, skip")
                errors += 1
                continue
            
            print(f"   📌 Oggetto: {oggetto}")
            
            # Manda via Brevo
            ok, resp = send_brevo(email, nome, oggetto, corpo)
            
            if ok:
                sent[email] = {
                    'nome': nome,
                    'settore': settore,
                    'citta': citta,
                    'oggetto': oggetto,
                    'sent_at': datetime.now().isoformat(),
                    'status': 'sent',
                    'follow_up_due': (datetime.now() + timedelta(days=3)).isoformat()
                }
                sent_today += 1
                print(f"   ✅ Inviata!")
            else:
                print(f"   ❌ Errore Brevo: {resp[:100]}")
                errors += 1
            
            # Pausa tra email (naturale, evita spam filter)
            time.sleep(random.uniform(30, 90))
            
        except Exception as e:
            print(f"   ❌ Errore: {e}")
            errors += 1
            continue
    
    save_sent(sent)
    
    print(f"\n{'='*50}")
    print(f"✅ Inviate oggi: {sent_today}")
    print(f"❌ Errori: {errors}")
    print(f"📊 Totale contattati: {len(sent)}")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    run_outreach()
