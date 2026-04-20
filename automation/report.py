#!/usr/bin/env python3
import os, json, subprocess, requests
from datetime import datetime, date, timedelta
from pathlib import Path
from anthropic import Anthropic

ANTHROPIC_KEY  = os.getenv('ANTHROPIC_API_KEY', '')
BREVO_KEY      = os.getenv('BREVO_API_KEY', '')
FROM_EMAIL     = 'r.fontana@creativemessadv.it'
FROM_NAME      = 'Riccardo Fontana — CEO'
ROBERTO_EMAIL  = os.getenv('ROBERTO_EMAIL', 'r.salvatori@creativemessadv.it')
INSTANTLY_KEY  = os.getenv('INSTANTLY_API_KEY', '')
DATA_DIR       = Path('data')
SENT_LOG       = DATA_DIR / 'sent.json'
TARGETS_FILE   = Path(__file__).resolve().parent.parent / 'data' / 'targets.json'

client = Anthropic(api_key=ANTHROPIC_KEY)

RICCARDO_PROMPT = """Sei Riccardo Fontana, CEO di Creative Mess ADV.
Scrivi report operativi a Roberto Salvatori (Presidente).
Stile: diretto, numeri precisi, niente giri di parole.
Se ci sono problemi: dilli chiaramente e dai il prossimo passo esatto.
Se tutto ok: confermalo e dai un insight utile.
Scrivi in italiano, tono professionale ma diretto. Max 200 parole.

IMPORTANTE: I processi cron (outreach-daily, scraper-daily, report-mattina, report-sera, briefing-settimanale)
mostrano stato "OK (eseguito)" o "stopped" dopo aver girato — e NORMALE, non e un errore.
Segnala problemi SOLO se exit_code != 0 o se ci sono errori nei log delle ultime 3 ore.
Se i log dicono "Nessun errore nelle ultime 3 ore" significa che tutto funziona."""

RICCARDO_WEEKLY = """Sei Riccardo Fontana, CEO di Creative Mess ADV.
Scrivi il briefing strategico settimanale a Roberto Salvatori (Presidente).
Obiettivo aziendale: 400.000 euro in 9 mesi.
Analizza i dati della settimana e dai:
1. Performance vs obiettivo (numeri precisi)
2. Cosa ha funzionato / cosa no
3. Una azione prioritaria da fare oggi
4. Riporta ESATTAMENTE la lista target che ti viene fornita, mantenendo i flag OK/ATTENZIONE/TODO. Mettila in fondo sotto il titolo MAPPA TARGET LOMBARDIA.
Stile: CEO che fa briefing al board. Numeri, analisi, decisioni. Max 300 parole + mappa target."""

CRON_JOBS = {'outreach-daily', 'scraper-daily', 'report-mattina', 'report-sera', 'briefing-settimanale'}

def get_pm2_status():
    try:
        result = subprocess.run(['pm2', 'jlist'], capture_output=True, text=True, timeout=10)
        processes = json.loads(result.stdout)
        status = []
        for p in processes:
            name = p.get('name', '')
            pm2_env = p.get('pm2_env', {})
            state = pm2_env.get('status', 'unknown')
            exits = pm2_env.get('exit_code', 0)
            if name in CRON_JOBS:
                label = 'OK (eseguito, in attesa prossimo cron)' if state == 'stopped' else state
            else:
                label = state
            status.append(f"{name}: {label} (exit_code: {exits})")
        return '\n'.join(status) if status else 'Nessun processo PM2'
    except Exception as e:
        return f'Errore lettura PM2: {e}'

def get_pm2_logs(lines=60):
    try:
        import re as _re
        result = subprocess.run(['pm2', 'logs', '--nostream', '--lines', str(lines)],
                                capture_output=True, text=True, timeout=10)
        log = result.stdout + result.stderr
        now = datetime.now()
        recent_errors = []
        for l in log.split('\n'):
            if not ('error' in l.lower() or 'errore' in l.lower() or 'traceback' in l.lower()):
                continue
            m = _re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', l)
            if m:
                for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                    try:
                        ts = datetime.strptime(m.group(), fmt)
                        if (now - ts).total_seconds() < 10800:
                            recent_errors.append(l)
                        break
                    except Exception:
                        continue
        return '\n'.join(recent_errors[:10]) if recent_errors else 'Nessun errore nelle ultime 3 ore'
    except Exception as e:
        return f'Log non disponibili: {e}'

def get_today_stats():
    today = date.today().isoformat()
    stats = {'email_oggi': 0, 'totale_pipeline': 0, 'prospect_nuovi': 0}
    if SENT_LOG.exists():
        try:
            sent = json.loads(SENT_LOG.read_text())
            stats['totale_pipeline'] = len(sent)
            for data in sent.values():
                ts = data.get('generated_at', '') or data.get('added_at', '')
                if ts.startswith(today):
                    stats['email_oggi'] += 1
        except Exception:
            pass
    for f in DATA_DIR.glob('prospect_*.json'):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date().isoformat()
            if mtime == today:
                stats['prospect_nuovi'] += len(json.loads(f.read_text()))
        except Exception:
            pass
    return stats

def get_weekly_instantly_stats():
    if not INSTANTLY_KEY:
        return 'INSTANTLY_API_KEY non configurata'
    try:
        headers = {'Authorization': f'Bearer {INSTANTLY_KEY}', 'Content-Type': 'application/json'}
        r = requests.get('https://api.instantly.ai/api/v2/campaigns',
                         params={'limit': 10}, headers=headers, timeout=10)
        if r.status_code == 200:
            campaigns = r.json().get('items', [])
            if not campaigns:
                return 'Nessuna campagna attiva'
            stats = []
            for c in campaigns:
                r2 = requests.get(f"https://api.instantly.ai/api/v2/campaigns/{c['id']}/analytics",
                                  headers=headers, timeout=10)
                if r2.status_code == 200:
                    a = r2.json()
                    stats.append(f"{c.get('name','')}: {a.get('total_leads',0)} lead, "
                                 f"{a.get('emails_sent',0)} inviate, "
                                 f"{a.get('open_rate',0):.1f}% aperture, "
                                 f"{a.get('reply_rate',0):.1f}% risposte")
            return '\n'.join(stats) if stats else 'Stats non disponibili'
        return f'Errore Instantly API: {r.status_code}'
    except Exception as e:
        return f'Errore stats Instantly: {e}'

def get_targets_status():
    if not TARGETS_FILE.exists():
        return f'targets.json non trovato in {TARGETS_FILE}'
    try:
        t = json.loads(TARGETS_FILE.read_text())
        targets = t.get('targets', [])
        idx = t.get('current_index', 0)
    except Exception as e:
        return f'Errore lettura targets: {e}'
    email_counts = {}
    if SENT_LOG.exists():
        try:
            sent = json.loads(SENT_LOG.read_text())
            for data in sent.values():
                key = f"{data.get('settore','')}|{data.get('citta','')}"
                email_counts[key] = email_counts.get(key, 0) + 1
        except Exception:
            pass
    lines = []
    for i, target in enumerate(targets):
        settore = target['settore']
        citta = target['citta']
        key = f"{settore}|{citta}"
        n_email = email_counts.get(key, 0)
        if n_email > 0:
            lines.append(f"OK {citta} - {settore} ({n_email} email)")
        elif i < idx:
            lines.append(f"ATTENZIONE {citta} - {settore} (scrappato, 0 email)")
        else:
            lines.append(f"TODO {citta} - {settore}")
    done = [l for l in lines if l.startswith('OK')]
    warn = [l for l in lines if l.startswith('ATTENZIONE')]
    todo = [l for l in lines if l.startswith('TODO')]
    result = f"COMPLETATI ({len(done)}/{len(targets)}):\n"
    result += '\n'.join(done) if done else '- nessuno ancora'
    if warn:
        result += '\n\nATTENZIONE:\n' + '\n'.join(warn)
    result += f'\n\nIN CODA ({len(todo)} rimanenti):\n'
    result += '\n'.join(todo[:25])
    if len(todo) > 25:
        result += f'\n... e altri {len(todo)-25} target'
    return result

def send_email(subject, body_html, body_text):
    if not BREVO_KEY:
        print("BREVO_API_KEY mancante"); return False
    payload = {
        'sender': {'name': FROM_NAME, 'email': FROM_EMAIL},
        'to': [{'email': ROBERTO_EMAIL, 'name': 'Roberto Salvatori'}],
        'subject': subject, 'htmlContent': body_html, 'textContent': body_text
    }
    try:
        r = requests.post('https://api.brevo.com/v3/smtp/email', json=payload,
                          headers={'api-key': BREVO_KEY, 'Content-Type': 'application/json'}, timeout=15)
        if r.status_code in (200, 201):
            print(f"Email inviata a {ROBERTO_EMAIL}"); return True
        else:
            print(f"Errore Brevo: {r.status_code} {r.text[:100]}"); return False
    except Exception as e:
        print(f"Errore invio: {e}"); return False

def format_html(text):
    lines = text.strip().split('\n')
    html = '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.7;color:#222;max-width:640px">'
    for line in lines:
        html += f'<p style="margin:8px 0">{line}</p>' if line.strip() else '<br>'
    html += '<hr style="margin:24px 0;border:none;border-top:1px solid #eee">'
    html += '<p style="font-size:12px;color:#999">Creative Mess ADV - Sistema AI Operativo</p></div>'
    return html

def generate_daily_report(slot):
    now = datetime.now()
    stats = get_today_stats()
    pm2 = get_pm2_status()
    logs = get_pm2_logs()
    periodo = 'mattina (06:00-13:00)' if slot == 'mattina' else 'pomeriggio (13:00-19:00)'
    data_context = f"""Report operativo {slot} - {now.strftime('%d/%m/%Y %H:%M')}
Periodo: {periodo}
OUTREACH OGGI:
- Email aggiunte a Instantly: {stats['email_oggi']}
- Totale pipeline: {stats['totale_pipeline']} contatti
- Nuovi prospect: {stats['prospect_nuovi']}
STATO PM2:
{pm2}
ERRORI LOG:
{logs}"""
    resp = client.messages.create(model='claude-opus-4-6', max_tokens=600, system=RICCARDO_PROMPT,
        messages=[{'role': 'user', 'content': f'Scrivi il report operativo {slot}:\n\n{data_context}'}])
    report_text = resp.content[0].text
    send_email(f"[{slot.upper()}] Report Operativo - {now.strftime('%d/%m/%Y')}",
               format_html(report_text), report_text)
    print(report_text)

def generate_weekly_briefing():
    now = datetime.now()
    stats = get_today_stats()
    instantly = get_weekly_instantly_stats()
    week_start = (now - timedelta(days=7)).strftime('%d/%m/%Y')
    week_end = now.strftime('%d/%m/%Y')
    sent_count_week = 0
    if SENT_LOG.exists():
        try:
            sent = json.loads(SENT_LOG.read_text())
            week_ago = (now - timedelta(days=7)).isoformat()
            for data in sent.values():
                ts = data.get('generated_at', '') or data.get('added_at', '')
                if ts >= week_ago:
                    sent_count_week += 1
        except Exception:
            pass
    targets_status = get_targets_status()
    data_context = f"""Briefing settimanale - {week_start} > {week_end}
PERFORMANCE:
- Lead aggiunti a Instantly: {sent_count_week}
- Totale pipeline: {stats['totale_pipeline']} contatti
- Prospect trovati: {stats['prospect_nuovi']}
STATS INSTANTLY:
{instantly}
STATO SISTEMA: {get_pm2_status()}
AVANZAMENTO TARGET:
{targets_status}"""
    resp = client.messages.create(model='claude-opus-4-6', max_tokens=1200, system=RICCARDO_WEEKLY,
        messages=[{'role': 'user', 'content': f'Scrivi il briefing settimanale:\n\n{data_context}'}])
    briefing_text = resp.content[0].text
    send_email(f"[BRIEFING SETTIMANALE] {week_start} > {week_end} - Riccardo CEO",
               format_html(briefing_text), briefing_text)
    print(briefing_text)

if __name__ == '__main__':
    import sys
    if not ANTHROPIC_KEY: print("ANTHROPIC_API_KEY mancante"); exit(1)
    if not BREVO_KEY: print("BREVO_API_KEY mancante"); exit(1)
    mode = sys.argv[1] if len(sys.argv) > 1 else 'mattina'
    if mode == 'weekly':
        print(f"\nBriefing settimanale - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        generate_weekly_briefing()
    else:
        print(f"\nReport {mode} - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        generate_daily_report(mode)
