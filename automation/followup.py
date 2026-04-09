#!/usr/bin/env python3
"""Follow-up automatico — 3 giorni dopo il primo contatto"""

import os, json, time, random, requests
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

ANTHROPIC_KEY = os.getenv('ANTHROPIC_API_KEY', '')
BREVO_KEY     = os.getenv('BREVO_API_KEY', '')
FROM_EMAIL    = os.getenv('FROM_EMAIL', 'roberto@creativemessadv.it')
FROM_NAME     = os.getenv('FROM_NAME', 'Roberto Salvatori — Creative Mess ADV')
DATA_DIR      = Path('data')
SENT_LOG      = DATA_DIR / 'sent.json'

client = Anthropic(api_key=ANTHROPIC_KEY)

FOLLOWUP_PROMPT = """Sei Chiara Benedetti di Creative Mess ADV.
Scrivi un follow-up breve (max 60 parole) a una cold email inviata 3 giorni fa.
Tono: naturale, non insistente. Ricorda brevemente la proposta precedente.
Aggiungi un elemento di valore (statistica, domanda, insight sul loro settore).
Formato:
OGGETTO: [oggetto follow-up]
---
[testo]"""

def send_brevo(to_email, to_name, oggetto, corpo):
    payload = {
        "sender": {"name": FROM_NAME, "email": FROM_EMAIL},
        "to": [{"email": to_email, "name": to_name}],
        "subject": oggetto,
        "htmlContent": corpo.replace('\n', '<br>'),
        "textContent": corpo
    }
    r = requests.post('https://api.brevo.com/v3/smtp/email', json=payload,
        headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'}, timeout=15)
    return r.status_code in (200, 201)

def run_followup():
    print(f"\n🔄 Follow-up automatico — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    if not SENT_LOG.exists():
        print("Nessun log trovato"); return
    
    sent = json.loads(SENT_LOG.read_text())
    now = datetime.now()
    done = 0
    
    for email, data in sent.items():
        if data.get('status') != 'sent':
            continue
        due = datetime.fromisoformat(data.get('follow_up_due', '2099-01-01'))
        if now < due:
            continue
        
        try:
            nome = data['nome']
            settore = data.get('settore', '')
            print(f"\n📧 Follow-up: {nome} ({email})")
            
            resp = client.messages.create(
                model='claude-opus-4-6', max_tokens=300,
                system=FOLLOWUP_PROMPT,
                messages=[{'role': 'user', 'content': f"Settore: {settore}\nNome: {nome}\nEmail precedente oggetto: {data.get('oggetto','')}"}]
            )
            raw = resp.content[0].text
            lines = raw.strip().split('\n')
            oggetto = next((l.replace('OGGETTO:','').strip() for l in lines if l.startswith('OGGETTO:')), 'Re: la mia email')
            corpo = '\n'.join(l for l in lines[lines.index('---')+1:] if lines.count('---') > 0).strip() if '---' in lines else raw
            
            if send_brevo(email, nome, oggetto, corpo):
                data['status'] = 'followup_sent'
                data['followup_at'] = now.isoformat()
                print(f"   ✅ Follow-up inviato!")
                done += 1
            
            time.sleep(random.uniform(30, 60))
        except Exception as e:
            print(f"   ❌ {e}")
    
    SENT_LOG.write_text(json.dumps(sent, ensure_ascii=False, indent=2))
    print(f"\n✅ Follow-up inviati: {done}")

if __name__ == '__main__':
    run_followup()
