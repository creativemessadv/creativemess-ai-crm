#!/usr/bin/env python3
"""
Report automatico di Riccardo — analizza attività del giorno e manda email a Roberto.
Gira alle 13:00 (report mattina) e alle 19:00 (report pomeriggio).
Il lunedì alle 07:00 genera il briefing strategico settimanale.
"""

import os, json, subprocess, smtplib, ssl
from datetime import datetime, date, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────
ANTHROPIC_KEY  = os.getenv('ANTHROPIC_API_KEY', '')
ZOHO_USER      = os.getenv('REPORT_FROM_EMAIL', 'r.fontana@creativemessadv.it')
ZOHO_PASS      = os.getenv('REPORT_ZOHO_PASS', '')
ROBERTO_EMAIL  = os.getenv('ROBERTO_EMAIL', 'r.salvatori@creativemessadv.it')
INSTANTLY_KEY  = os.getenv('INSTANTLY_API_KEY', '')
DATA_DIR       = Path('data')
SENT_LOG       = DATA_DIR / 'sent.json'

client = Anthropic(api_key=ANTHROPIC_KEY)

RICCARDO_PROMPT = """Sei Riccardo Fontana, CEO di Creative Mess ADV.
Scrivi report operativi a Roberto Salvatori (Presidente).
Stile: diretto, numeri precisi, niente giri di parole.
Se ci sono problemi: dilli chiaramente e dai il prossimo passo esatto.
Se tutto ok: confermalo e dai un insight utile.
Scrivi in italiano, tono professionale ma diretto. Max 200 parole."""

RICCARDO_WEEKLY = """Sei Riccardo Fontana, CEO di Creative Mess ADV.
Scrivi il briefing strategico settimanale a Roberto Salvatori (Presidente).
Obiettivo aziendale: €400.000 in 9 mesi.
Analizza i dati della settimana e dai:
1. Performance vs obiettivo
2. Cosa ha funzionato / cosa no
3. Target settori/città per la prossima settimana (sii specifico: "dentisti Roma", "avvocati Milano")
4. Una azione prioritaria da fare oggi
Stile: CEO che fa briefing al board. Numeri, analisi, decisioni. Max 300 parole."""

# ── DATA COLLECTION ───────────────────────────────────────────────────────────

def get_pm2_status():
    """Legge stato processi PM2"""
    try:
        result = subprocess.run(
            ['pm2', 'jlist'],
            capture_output=True, text=True, timeout=10
        )
        processes = json.loads(result.stdout)
        status = []
        for p in processes:
            name   = p.get('name', '')
            pm2_env = p.get('pm2_env', {})
            state  = pm2_env.get('status', 'unknown')
            exits  = pm2_env.get('exit_code', 0)
            restarts = p.get('pm2_env', {}).get('restart_time', 0)
            status.append(f"{name}: {state} (uscite: {exits}, restart: {restarts})")
        return '\n'.join(status) if status else 'Nessun processo PM2'
    except Exception as e:
        return f'Errore lettura PM2: {e}'

def get_pm2_logs(lines=30):
    """Legge ultimi log PM2 per errori"""
    try:
        result = subprocess.run(
            ['pm2', 'logs', '--nostream', '--lines', str(lines)],
            capture_output=True, text=True, timeout=10
        )
        log = result.stdout + result.stderr
        # Cerca errori
        errors = [l for l in log.split('\n') if 'error' in l.lower() or 'errore' in l.lower() or 'traceback' in l.lower()]
        return '\n'.join(errors[:10]) if errors else 'Nessun errore nei log'
    except Exception as e:
        return f'Log non disponibili: {e}'

def get_today_stats():
    """Statistiche outreach di oggi"""
    today = date.today().isoformat()
    stats = {
        'email_oggi': 0,
        'totale_pipeline': 0,
        'prospect_nuovi': 0,
        'errori_outreach': 0
    }

    # Leggi sent.json
    if SENT_LOG.exists():
        try:
            sent = json.loads(SENT_LOG.read_text())
            stats['totale_pipeline'] = len(sent)
            for data in sent.values():
                added = data.get('added_at', '')
                if added.startswith(today):
                    stats['email_oggi'] += 1
        except Exception:
            pass

    # Prospect trovati oggi
    for f in DATA_DIR.glob('prospect_*.json'):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date().isoformat()
            if mtime == today:
                data = json.loads(f.read_text())
                stats['prospect_nuovi'] += len(data)
        except Exception:
            pass

    return stats

def get_weekly_instantly_stats():
    """Statistiche campagna Instantly dell'ultima settimana"""
    if not INSTANTLY_KEY:
        return 'INSTANTLY_API_KEY non configurata'
    try:
        import requests
        headers = {
            'Authorization': f'Bearer {INSTANTLY_KEY}',
            'Content-Type': 'application/json'
        }
        r = requests.get(
            'https://api.instantly.ai/api/v2/campaigns',
            params={'limit': 10},
            headers=headers, timeout=10
        )
        if r.status_code == 200:
            campaigns = r.json().get('items', [])
            if not campaigns:
                return 'Nessuna campagna attiva'
            stats = []
            for c in campaigns:
                name = c.get('name', '')
                # Prova a leggere analytics
                r2 = requests.get(
                    f"https://api.instantly.ai/api/v2/campaigns/{c['id']}/analytics",
                    headers=headers, timeout=10
                )
                if r2.status_code == 200:
                    a = r2.json()
                    stats.append(
                        f"{name}: {a.get('total_leads',0)} lead, "
                        f"{a.get('emails_sent',0)} inviate, "
                        f"{a.get('open_rate',0):.1f}% aperture, "
                        f"{a.get('reply_rate',0):.1f}% risposte"
                    )
            return '\n'.join(stats) if stats else 'Stats non disponibili'
        return f'Errore Instantly API: {r.status_code}'
    except Exception as e:
        return f'Errore stats Instantly: {e}'

def get_targets():
    """Legge target settori/città configurati"""
    targets_file = DATA_DIR / 'targets.json'
    if targets_file.exists():
        try:
            t = json.loads(targets_file.read_text())
            return ', '.join([f"{x['settore']} {x['citta']}" for x in t.get('targets', [])])
        except Exception:
            pass
    return 'ristoranti Milano (default)'

# ── EMAIL SENDING ─────────────────────────────────────────────────────────────

def send_email(subject, body_html, body_text):
    """Manda email via Zoho SMTP"""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = f'Riccardo Fontana — CEO <{ZOHO_USER}>'
    msg['To']      = ROBERTO_EMAIL

    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL('smtp.zoho.eu', 465, context=context) as server:
            server.login(ZOHO_USER, ZOHO_PASS)
            server.sendmail(ZOHO_USER, ROBERTO_EMAIL, msg.as_string())
        print(f"✅ Email inviata a {ROBERTO_EMAIL}")
        return True
    except Exception as e:
        print(f"❌ Errore invio email: {e}")
        return False

def format_html(text):
    """Converte testo in HTML semplice"""
    lines = text.strip().split('\n')
    html = '<div style="font-family:Arial,sans-serif;font-size:14px;line-height:1.7;color:#222;max-width:640px">'
    for line in lines:
        if line.strip():
            html += f'<p style="margin:8px 0">{line}</p>'
        else:
            html += '<br>'
    html += '<hr style="margin:24px 0;border:none;border-top:1px solid #eee">'
    html += '<p style="font-size:12px;color:#999">Creative Mess ADV — Sistema AI Operativo</p>'
    html += '</div>'
    return html

# ── REPORT GENERATION ─────────────────────────────────────────────────────────

def generate_daily_report(slot):
    """Genera e manda report giornaliero (mattina=13:00 / pomeriggio=19:00)"""
    now   = datetime.now()
    stats = get_today_stats()
    pm2   = get_pm2_status()
    logs  = get_pm2_logs()

    periodo = 'mattina (06:00-13:00)' if slot == 'mattina' else 'pomeriggio (13:00-19:00)'

    data_context = f"""Report operativo {slot} — {now.strftime('%d/%m/%Y %H:%M')}
Periodo analizzato: {periodo}

ATTIVITÀ OUTREACH OGGI:
- Email/lead aggiunti a Instantly: {stats['email_oggi']}
- Totale pipeline: {stats['totale_pipeline']} contatti
- Nuovi prospect trovati: {stats['prospect_nuovi']}

TARGET ATTIVI: {get_targets()}

STATO PROCESSI PM2:
{pm2}

ERRORI NEI LOG:
{logs}"""

    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=600,
        system=RICCARDO_PROMPT,
        messages=[{'role': 'user', 'content':
            f'Scrivi il report operativo {slot} per Roberto basandoti su questi dati:\n\n{data_context}'}]
    )
    report_text = resp.content[0].text

    subject = f"[{slot.upper()}] Report Operativo — {now.strftime('%d/%m/%Y')}"
    send_email(subject, format_html(report_text), report_text)
    print(report_text)

def generate_weekly_briefing():
    """Genera e manda briefing strategico settimanale (lunedì 07:00)"""
    now          = datetime.now()
    stats        = get_today_stats()
    instantly    = get_weekly_instantly_stats()
    targets      = get_targets()

    # Calcola settimana
    week_start = (now - timedelta(days=7)).strftime('%d/%m/%Y')
    week_end   = now.strftime('%d/%m/%Y')

    # Leggi storico settimana
    sent_count_week = 0
    if SENT_LOG.exists():
        try:
            sent = json.loads(SENT_LOG.read_text())
            week_ago = (now - timedelta(days=7)).isoformat()
            for data in sent.values():
                if data.get('added_at', '') >= week_ago:
                    sent_count_week += 1
        except Exception:
            pass

    data_context = f"""Briefing settimanale — {week_start} → {week_end}

PERFORMANCE SETTIMANA:
- Lead aggiunti a Instantly: {sent_count_week}
- Totale pipeline: {stats['totale_pipeline']} contatti
- Nuovi prospect trovati: {stats['prospect_nuovi']}

STATS CAMPAGNA INSTANTLY:
{instantly}

TARGET CORRENTI: {targets}

STATO SISTEMA: {get_pm2_status()}"""

    resp = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=800,
        system=RICCARDO_WEEKLY,
        messages=[{'role': 'user', 'content':
            f'Scrivi il briefing strategico settimanale per Roberto:\n\n{data_context}'}]
    )
    briefing_text = resp.content[0].text

    subject = f"[BRIEFING SETTIMANALE] {week_start} → {week_end} — Riccardo CEO"
    send_email(subject, format_html(briefing_text), briefing_text)
    print(briefing_text)

# ── MAIN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); exit(1)
    if not ZOHO_PASS:
        print("❌ REPORT_ZOHO_PASS mancante"); exit(1)

    mode = sys.argv[1] if len(sys.argv) > 1 else 'mattina'

    if mode == 'weekly':
        print(f"\n📊 Briefing settimanale — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        generate_weekly_briefing()
    else:
        print(f"\n📋 Report {mode} — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        generate_daily_report(mode)
