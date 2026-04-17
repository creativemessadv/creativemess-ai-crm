#!/usr/bin/env python3
import os, json, time, random, csv, subprocess, requests
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

ANTHROPIC_KEY         = os.getenv('ANTHROPIC_API_KEY', '')
INSTANTLY_KEY         = os.getenv('INSTANTLY_API_KEY', '')
INSTANTLY_CAMPAIGN_ID = os.getenv('INSTANTLY_CAMPAIGN_ID', '')
DAILY_LIMIT           = int(os.getenv('DAILY_LIMIT', '50'))
DATA_DIR              = Path('data')
SENT_LOG              = DATA_DIR / 'sent.json'
OUTREACH_DIR          = DATA_DIR / 'outreach'

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
        model='claude-haiku-4-5-20251001', max_tokens=400, system=CHIARA_PROMPT,
        messages=[{'role': 'user', 'content': context}]
    )
    return resp.content[0].text

def generate_followup(nome, settore, oggetto_orig):
    resp = client.messages.create(
        model='claude-haiku-4-5-20251001', max_tokens=300, system=FOLLOWUP_PROMPT,
        messages=[{'role': 'user', 'content':
            f"Settore: {settore}\nNome azienda: {nome}\nOggetto email precedente: {oggetto_orig}"}]
    )
    return resp.content[0].text

def parse_email(text):
    lines = text.strip().split('\n')
    oggetto, corpo_lines, after = '', [], False
    for line in lines:
        clean = line.strip().lstrip('*').rstrip('*').strip()
        if clean.startswith('OGGETTO:'):
            oggetto = clean.replace('OGGETTO:', '').strip()
        elif line.strip() in ('---', '—--', '———'):
            after = True
        elif after:
            corpo_lines.append(line)
    return oggetto, '\n'.join(corpo_lines).strip()

def upload_to_instantly(rows):
    """Carica lead su Instantly API v2"""
    if not INSTANTLY_KEY or not INSTANTLY_CAMPAIGN_ID:
        print("   INSTANTLY_KEY o CAMPAIGN_ID mancante — skip upload")
        return 0
    headers = {'Authorization': f'Bearer {INSTANTLY_KEY}', 'Content-Type': 'application/json'}
    uploaded = 0
    for row in rows:
        lead = {
            'email':           row['email'].strip(),
            'first_name':      row.get('first_name', '').strip(),
            'last_name':       row.get('last_name', '').strip(),
            'company_name':    row.get('company_name', '').strip(),
            'website':         row.get('website', '').strip(),
            'personalization': row.get('body', ''),
            'custom_variables': {
                'subject':          row.get('subject', ''),
                'body':             row.get('body', ''),
                'followup_subject': row.get('followup_subject', ''),
                'followup_body':    row.get('followup_body', ''),
                'city':             row.get('city', ''),
            }
        }
        try:
            r = requests.post(
                'https://api.instantly.ai/api/v2/leads',
                json={'campaign_id': INSTANTLY_CAMPAIGN_ID, **lead},
                headers=headers, timeout=30
            )
            if r.status_code in (200, 201):
                uploaded += 1
            else:
                print(f"   Errore {row['email']}: {r.status_code} {r.text[:80]}")
        except Exception as e:
            print(f"   Errore {row['email']}: {e}")
    return uploaded


def _run_scraper():
    print("   🗺️  Lancio scraper per prossimo target...")
    try:
        result = subprocess.run(['python3', 'scraper.py', '--auto', '--n', '400'],
                                timeout=900, capture_output=False)
        if result.returncode != 0:
            print("   ⚠️  Scraper terminato con errore")
    except subprocess.TimeoutExpired:
        print("   ⏱️  Scraper timeout — continuo con quello che c'è")
    except Exception as e:
        print(f"   ❌ Errore scraper: {e}")

def run_outreach():
    print(f"\n{'='*55}")
    print(f"✍️  Generazione email — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print(f"{'='*55}")
    if not ANTHROPIC_KEY:
        print("❌ ANTHROPIC_API_KEY mancante"); return

    sent = load_sent()
    prospects = load_prospects()
    to_contact = [p for p in prospects if p.get('email') and p['email'] not in sent]

    print(f"📋 Prospect disponibili: {len(to_contact)}")
    print(f"📤 Da processare oggi: {min(DAILY_LIMIT, len(to_contact))}")

    if not to_contact:
        print("⚠️  Nessun nuovo prospect — lancio scraper automaticamente...")
        _run_scraper()
        prospects = load_prospects()
        sent = load_sent()
        to_contact = [p for p in prospects if p.get('email') and p['email'] not in sent]
        if not to_contact:
            print("⚠️  Ancora nessun prospect dopo scraper, riprova domani"); return

    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    csv_path  = OUTREACH_DIR / f'batch_{timestamp}.csv'
    rows, processed, errors = [], 0, 0

    for p in to_contact[:DAILY_LIMIT]:
        nome=p.get('nome','Azienda'); email=p['email']
        settore=p.get('settore',''); citta=p.get('citta',''); sito=p.get('sito','')
        print(f"\n📧 {nome} ({email})")
        try:
            print(f"   ✍️  Chiara genera email...")
            raw = generate_email(nome, settore, citta, sito)
            subj, body = parse_email(raw)
            if not subj or not body:
                print(f"   ⚠️  Email non valida, skip"); errors += 1; continue
            fu_raw = generate_followup(nome, settore, subj)
            fu_subj, fu_body = parse_email(fu_raw)
            if not fu_subj:
                fu_subj = f"Re: {subj}"; fu_body = fu_raw
            print(f"   📌 {subj}")
            rows.append({'email':email,'first_name':nome.split()[0] if nome else '',
                'last_name':' '.join(nome.split()[1:]) if len(nome.split())>1 else '',
                'company_name':nome,'city':citta,'website':sito,
                'subject':subj,'body':body,'followup_subject':fu_subj,'followup_body':fu_body})
            sent[email] = {'nome':nome,'settore':settore,'citta':citta,'oggetto':subj,
                'generated_at':datetime.now().isoformat(),'status':'uploaded','csv':str(csv_path)}
            processed += 1; print(f"   ✅ Pronto!")
        except Exception as e:
            print(f"   ❌ {e}"); errors += 1; continue
        time.sleep(random.uniform(2, 5))

    if processed < DAILY_LIMIT:
        mancanti = DAILY_LIMIT - processed
        print(f"\n⚡ Processati {processed}/{DAILY_LIMIT} — cerco altri {mancanti} prospect...")
        _run_scraper()
        sent_ag = load_sent()
        nuovi = [p for p in load_prospects() if p.get('email') and p['email'] not in sent_ag]
        if nuovi:
            print(f"   Trovati {len(nuovi)} nuovi prospect, genero altre email...")
            for p in nuovi[:mancanti]:
                nome=p.get('nome','Azienda'); email=p['email']
                settore=p.get('settore',''); citta=p.get('citta',''); sito=p.get('sito','')
                print(f"\n📧 {nome} ({email})")
                try:
                    raw = generate_email(nome, settore, citta, sito)
                    subj, body = parse_email(raw)
                    if not subj or not body: errors += 1; continue
                    fu_raw = generate_followup(nome, settore, subj)
                    fu_subj, fu_body = parse_email(fu_raw)
                    if not fu_subj: fu_subj=f"Re: {subj}"; fu_body=fu_raw
                    print(f"   📌 {subj}")
                    rows.append({'email':email,'first_name':nome.split()[0] if nome else '',
                        'last_name':' '.join(nome.split()[1:]) if len(nome.split())>1 else '',
                        'company_name':nome,'city':citta,'website':sito,
                        'subject':subj,'body':body,'followup_subject':fu_subj,'followup_body':fu_body})
                    sent[email]={'nome':nome,'settore':settore,'citta':citta,'oggetto':subj,
                        'generated_at':datetime.now().isoformat(),'status':'uploaded','csv':str(csv_path)}
                    processed += 1; print(f"   ✅ Pronto!")
                except Exception as e:
                    print(f"   ❌ {e}"); errors += 1
                time.sleep(random.uniform(2, 5))

    if rows:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader(); writer.writerows(rows)
        print(f"\n📊 CSV backup salvato: {csv_path}")
        print(f"\n🚀 Caricamento su Instantly...")
        n_uploaded = upload_to_instantly(rows)
        if n_uploaded:
            print(f"   ✅ {n_uploaded}/{len(rows)} lead caricati su Instantly")
        else:
            print(f"   ⚠️  Upload fallito — carica manualmente il CSV su Instantly")

    save_sent(sent)
    print(f"\n{'='*55}")
    print(f"✅ Email generate: {processed}")
    print(f"❌ Errori: {errors}")
    print(f"📊 Totale processati: {len(sent)}")
    print(f"{'='*55}\n")

if __name__ == '__main__':
    run_outreach()
