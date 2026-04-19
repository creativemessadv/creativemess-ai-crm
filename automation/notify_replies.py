#!/usr/bin/env python3
import os, json, requests
from datetime import datetime
from pathlib import Path

INSTANTLY_KEY  = os.getenv('INSTANTLY_API_KEY', '')
BREVO_KEY      = os.getenv('BREVO_API_KEY', '')
ROBERTO_EMAIL  = os.getenv('ROBERTO_EMAIL', 'r.salvatori@creativemessadv.it')
DATA_DIR       = Path('data')
CHECK_FILE     = DATA_DIR / 'last_reply_check.json'

def load_seen():
    if CHECK_FILE.exists():
        try:
            return set(json.loads(CHECK_FILE.read_text()).get('seen_ids', []))
        except Exception:
            pass
    return set()

def save_seen(seen):
    DATA_DIR.mkdir(exist_ok=True)
    CHECK_FILE.write_text(json.dumps({'seen_ids': list(seen)[-2000:]}, indent=2))

def get_received_emails():
    if not INSTANTLY_KEY:
        return []
    h = {'Authorization': f'Bearer {INSTANTLY_KEY}', 'Content-Type': 'application/json'}
    try:
        r = requests.get('https://api.instantly.ai/api/v2/emails',
                         params={'limit': 50, 'email_type': 'received'},
                         headers=h, timeout=15)
        if r.status_code == 200:
            return r.json().get('items', [])
        print(f'Errore API Instantly: {r.status_code} {r.text[:100]}')
    except Exception as e:
        print(f'Errore connessione: {e}')
    return []

def send_notification(emails):
    if not BREVO_KEY:
        print('BREVO_KEY mancante'); return
    now = datetime.now().strftime('%d/%m/%Y %H:%M')
    blocks = ''
    for e in emails:
        from_email = e.get('from_address_email', 'sconosciuto')
        subject    = e.get('subject', '(nessun oggetto)')
        body_raw   = e.get('body', {})
        body_text  = body_raw.get('text', body_raw.get('html', '')) if isinstance(body_raw, dict) else str(body_raw)
        body_escaped = body_text.replace('<','&lt;').replace('>','&gt;')[:1500]
        ts         = e.get('timestamp_email', e.get('timestamp_created', ''))[:16].replace('T',' ')
        blocks += f'''
<div style="background:#f0f7ff;border-left:4px solid #2563eb;padding:16px;margin:16px 0;border-radius:6px">
  <p style="margin:0 0 6px 0"><strong>Da:</strong> {from_email}</p>
  <p style="margin:0 0 6px 0"><strong>Oggetto:</strong> {subject}</p>
  <p style="margin:0 0 10px 0"><strong>Ricevuta:</strong> {ts}</p>
  <blockquote style="background:#fff;border-left:3px solid #93c5fd;padding:10px;margin:8px 0;font-style:italic;white-space:pre-wrap">{body_escaped}</blockquote>
</div>'''

    html = f'''<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.8;color:#222;max-width:640px">
<h3 style="color:#d32f2f">Risposta ricevuta — {now}</h3>
<p>Ciao Roberto,<br>{"uno" if len(emails)==1 else str(len(emails))} prospect {"ha" if len(emails)==1 else "hanno"} risposto a Chiara:</p>
{blocks}
<p><a href="https://app.instantly.ai/app/unibox" style="background:#2563eb;color:#fff;padding:10px 20px;text-decoration:none;border-radius:4px">Rispondi su Instantly → Unibox</a></p>
<hr style="margin:20px 0;border:none;border-top:1px solid #eee">
<p style="font-size:12px;color:#999">Riccardo Fontana — Creative Mess ADV</p>
</div>'''

    subject_line = f'[RISPOSTA] {emails[0].get("from_address_email","")} ha risposto a Chiara' if len(emails)==1 else f'[{len(emails)} RISPOSTE] Nuove risposte a Chiara'
    payload = {
        'sender': {'name': 'Riccardo Fontana — CEO', 'email': 'r.fontana@creativemessadv.it'},
        'to': [{'email': ROBERTO_EMAIL}],
        'subject': subject_line,
        'htmlContent': html
    }
    try:
        r = requests.post('https://api.brevo.com/v3/smtp/email', json=payload,
                          headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'}, timeout=15)
        if r.status_code in (200, 201):
            print(f'Notifica inviata: {len(emails)} risposta/e')
        else:
            print(f'Errore Brevo: {r.status_code} {r.text[:100]}')
    except Exception as e:
        print(f'Errore invio: {e}')

def check_replies():
    print(f'[{datetime.now().strftime("%d/%m/%Y %H:%M:%S")}] Controllo risposte Instantly...')
    if not INSTANTLY_KEY:
        print('INSTANTLY_API_KEY mancante'); return
    seen = load_seen()
    emails = get_received_emails()
    print(f'  Email ricevute totali: {len(emails)}')
    new_emails = [e for e in emails if e.get('id') and e['id'] not in seen]
    if new_emails:
        print(f'  Nuove risposte: {len(new_emails)}')
        send_notification(new_emails)
        for e in new_emails:
            seen.add(e['id'])
    else:
        print('  Nessuna nuova risposta')
    save_seen(seen)

if __name__ == '__main__':
    check_replies()
