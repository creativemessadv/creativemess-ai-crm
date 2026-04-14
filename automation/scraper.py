#!/usr/bin/env python3
"""
Google Maps scraper via Apify — trova aziende italiane con email
Uso: python3 scraper.py --settore "ristoranti" --citta "Milano" --n 50
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

APIFY_TOKEN  = os.getenv('APIFY_API_KEY', '')
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

def run_apify_gmaps(settore, citta, max_results):
    """Lancia Apify Google Maps Scraper e ritorna i risultati"""
    if not APIFY_TOKEN:
        print("❌ APIFY_API_KEY mancante nel .env")
        return []

    print(f"🗺️  Avvio Apify Google Maps: {settore} a {citta} (max {max_results})")

    # Actor: microworlds/crawler-google-places ($1.50/1000 vs $145/1000 del compass)
    actor_id = 'microworlds~crawler-google-places'
    run_url   = f'https://api.apify.com/v2/acts/{actor_id}/runs?token={APIFY_TOKEN}'

    payload = {
        'searchStringsArray': [settore],
        'locationQuery': f'{citta}, Italy',
        'maxCrawledPlaces': max_results,
        'language': 'it',
        'countryCode': 'it',
        'includeHistogram': False,
        'includeOpeningHours': False,
        'includePeopleAlsoSearch': False,
        'maxImages': 0,
        'maxReviews': 0,
    }

    try:
        r = requests.post(run_url, json=payload, timeout=30)
        r.raise_for_status()
        run_data  = r.json()
        run_id    = run_data['data']['id']
        dataset_id = run_data['data']['defaultDatasetId']
        print(f"   Run ID: {run_id}")
    except Exception as e:
        print(f"❌ Errore avvio Apify: {e}")
        return []

    # Aspetta completamento (polling ogni 15s, max 10 min)
    status_url = f'https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}'
    print("   Aspetto risultati", end='', flush=True)
    for _ in range(40):
        time.sleep(15)
        print('.', end='', flush=True)
        try:
            s = requests.get(status_url, timeout=10).json()
            status = s['data']['status']
            if status == 'SUCCEEDED':
                print(' ✅')
                break
            elif status in ('FAILED', 'ABORTED', 'TIMED-OUT'):
                print(f' ❌ {status}')
                return []
        except Exception:
            pass
    else:
        print(' ⏱️ timeout')
        return []

    # Scarica dataset
    dataset_url = f'https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_TOKEN}&format=json'
    try:
        items = requests.get(dataset_url, timeout=30).json()
    except Exception as e:
        print(f"❌ Errore download dataset: {e}")
        return []

    print(f"   Scaricati {len(items)} risultati")
    return items

def parse_apify_results(items, settore, citta):
    """Converte output Apify nel formato prospect standard"""
    results = []
    for item in items:
        try:
            nome     = item.get('title', '') or item.get('name', '')
            if not nome:
                continue

            indirizzo = item.get('address', '') or item.get('street', '') or citta
            telefono  = item.get('phone', '') or item.get('phoneUnformatted', '')
            sito      = item.get('website', '') or ''
            # Rimuovi trailing slash e parametri tracking
            if sito:
                sito = sito.split('?')[0].rstrip('/')

            # Email: Apify a volte la include già
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
                'gmaps_url': item.get('url', ''),
                'rating': item.get('totalScore', ''),
                'reviews': item.get('reviewsCount', 0),
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

    items   = run_apify_gmaps(settore, citta, args.n)
    results = parse_apify_results(items, settore, citta)

    if results and not args.no_email_search:
        results = find_missing_emails(results)

    save_results(results, args.settore, args.citta)
