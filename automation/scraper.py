#!/usr/bin/env python3
"""
Google Maps scraper via Outscraper — trova aziende italiane con email
Uso: python3 scraper.py --settore "ristoranti" --citta "Milano" --n 50
Costo: $3 per 1.000 risultati (prezzo fisso per risultato, niente sorprese)
"""

import requests
import time
import random
import json
import re
import argparse
import os
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

OUTSCRAPER_KEY = os.getenv('OUTSCRAPER_API_KEY', '')
HEADERS_WEB  = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept-Language': 'it-IT,it;q=0.9',
}
BAD_EMAILS = ['esempio', 'example', 'noreply', 'no-reply', 'privacy@', 'dpo@',
              'sentry', 'wixpress', '.png', '.jpg', 'webmaster@', 'support@']

def is_good_email(e):
    e = e.lower()
    return bool(re.match(r'^[^@]+@[^@]+\.[^@]{2,}$', e)) and not any(b in e for b in BAD_EMAILS)

def find_email_on_site(base_url):
    """Cerca email su homepage + /contatti + /contact"""
    if not base_url or not base_url.startswith('http'):
        return ''
    domain = urlparse(base_url).netloc.replace('www.', '')
    pages = ['', '/contatti', '/contattaci', '/contact', '/chi-siamo', '/about']
    all_emails = []
    for path in pages:
        url = base_url.rstrip('/') + path if path else base_url
        try:
            r = requests.get(url, headers=HEADERS_WEB, timeout=8,
                             allow_redirects=True, verify=False)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
                e = a['href'].replace('mailto:', '').split('?')[0].strip().lower()
                if e and is_good_email(e):
                    if domain in e:
                        return e
                    all_emails.append(e)
            for e in re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', r.text):
                e = e.lower()
                if is_good_email(e):
                    if domain in e:
                        return e
                    all_emails.append(e)
            if all_emails and path:
                break
        except Exception:
            pass
        time.sleep(random.uniform(0.5, 1.0))
    for e in all_emails:
        if domain in e:
            return e
    return all_emails[0] if all_emails else ''

def run_outscraper_gmaps(settore, citta, max_results):
    """Cerca aziende su Google Maps via Outscraper — $3 per 1.000 risultati"""
    if not OUTSCRAPER_KEY:
        print("❌ OUTSCRAPER_API_KEY mancante nel .env")
        return []

    print(f"🗺️  Outscraper Google Maps: {settore} a {citta} (max {max_results})")

    query   = f"{settore}, {citta}, Italy"
    headers = {'X-API-KEY': OUTSCRAPER_KEY}

    # Per >199 risultati usa modalità asincrona con polling
    use_async = max_results > 199

    try:
        r = requests.get(
            'https://api.app.outscraper.com/maps/search-v2',
            params={
                'query':    query,
                'limit':    max_results,
                'language': 'it',
                'region':   'IT',
                'async':    'true' if use_async else 'false',
            },
            headers=headers,
            timeout=120
        )
        r.raise_for_status()
        data = r.json()

        if not use_async:
            results = data.get('data', [[]])[0] if data.get('data') else []
            print(f"   ✅ {len(results)} risultati")
            return results

        # Modalità asincrona — polling finché non è pronto
        task_id = data.get('id', '')
        if not task_id:
            print(f"❌ Task ID mancante: {data}")
            return []

        print(f"   Task ID: {task_id} — aspetto risultati", end='', flush=True)
        for _ in range(60):  # max 15 minuti
            time.sleep(15)
            print('.', end='', flush=True)
            try:
                poll = requests.get(
                    f'https://api.app.outscraper.com/requests/{task_id}',
                    headers=headers, timeout=30
                ).json()
                status = poll.get('status', '')
                if status == 'Success':
                    print(' ✅')
                    results = poll.get('data', [[]])[0] if poll.get('data') else []
                    print(f"   ✅ {len(results)} risultati scaricati")
                    return results
                elif status in ('Failed', 'Cancelled'):
                    print(f' ❌ {status}')
                    return []
            except Exception:
                pass
        print(' ⏱️ timeout')
        return []

    except Exception as e:
        print(f"❌ Errore Outscraper: {e}")
        return []

    print(f"   ✅ Totale scaricati: {len(all_items)}")
    return all_items

def parse_outscraper_results(items, settore, citta):
    """Converte output Outscraper nel formato prospect standard"""
    results = []
    for item in items:
        try:
            nome = item.get('name', '')
            if not nome:
                continue

            indirizzo = item.get('full_address', '') or item.get('address', '') or citta
            telefono  = item.get('phone', '') or ''
            sito      = item.get('site', '') or item.get('website', '') or ''
            if sito:
                sito = sito.split('?')[0].rstrip('/')

            email = item.get('email', '') or ''
            if email and not is_good_email(email):
                email = ''

            results.append({
                'nome': nome.strip(),
                'settore': settore,
                'citta': citta,
                'indirizzo': indirizzo,
                'telefono': telefono,
                'sito': sito,
                'email': email,
                'email_trovata': bool(email),
                'gmaps_url': item.get('place_id', ''),
                'rating': item.get('rating', ''),
                'reviews': item.get('reviews', 0),
                'scraped_at': datetime.now().isoformat()
            })

            status = '✉️' if email else '🌐' if sito else '📞' if telefono else '📋'
            print(f"  {status} {nome[:50]} | {indirizzo[:40]}")

        except Exception:
            continue

    return results

def find_missing_emails(results):
    """Per aziende senza email, crawla il sito web"""
    no_email = [r for r in results if not r['email'] and r.get('sito')]
    print(f"\n📧 Cerco email per {len(no_email)} aziende con sito web...")

    for r in no_email:
        print(f"  🔎 {r['nome'][:40]} ({r['sito'][:50]})")
        email = find_email_on_site(r['sito'])
        if email:
            r['email'] = email
            r['email_trovata'] = True
            print(f"     ✅ {email}")
        else:
            print(f"     — non trovata")
        time.sleep(random.uniform(1, 2))

    return results

def save_results(results, settore, citta):
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    base = f"data/prospect_{settore.replace(' ','_')}_{citta.replace(' ','_')}_{timestamp}"

    with open(f"{base}.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(f"{base}.csv", 'w', encoding='utf-8') as f:
        f.write("Nome,Settore,Città,Email,Telefono,Sito,Rating,Reviews\n")
        for r in results:
            f.write(f'"{r["nome"]}","{r["settore"]}","{r["citta"]}","{r.get("email","")}","'
                    f'{r.get("telefono","")}","{r.get("sito","")}","{r.get("rating","")}","{r.get("reviews","")}"\n')

    con_email = sum(1 for r in results if r.get('email'))
    print(f"\n✅ Salvati {len(results)} prospect ({con_email} con email)")
    print(f"   📄 {base}.json")
    print(f"   📊 {base}.csv")
    return base

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    parser = argparse.ArgumentParser()
    parser.add_argument('--settore', default='', help='Settore (es. ristoranti, dentisti)')
    parser.add_argument('--citta',   default='', help='Città')
    parser.add_argument('--n',       type=int, default=100, help='Numero massimo risultati')
    parser.add_argument('--no-email-search', action='store_true', help='Salta crawl email dai siti')
    parser.add_argument('--auto', action='store_true', help='Legge target da data/targets.json e avanza indice')
    args = parser.parse_args()

    settore, citta = args.settore, args.citta

    if args.auto or (not settore and not citta):
        targets_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'targets.json')
        targets_file = os.path.normpath(targets_file)
        try:
            with open(targets_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            targets = data['targets']
            idx     = data.get('current_index', 0) % len(targets)
            target  = targets[idx]
            settore = target['settore']
            citta   = target['citta']
            # Avanza indice per il giorno dopo
            data['current_index'] = (idx + 1) % len(targets)
            with open(targets_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"🎯 Target del giorno: {settore} a {citta} (#{idx+1}/{len(targets)})")
        except Exception as e:
            print(f"❌ Errore lettura targets.json: {e}")
            settore, citta = 'ristoranti', 'Milano'

    items   = run_outscraper_gmaps(settore, citta, args.n)
    results = parse_outscraper_results(items, settore, citta)

    if results and not args.no_email_search:
        results = find_missing_emails(results)

    save_results(results, args.settore, args.citta)
