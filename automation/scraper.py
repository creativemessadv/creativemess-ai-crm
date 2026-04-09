#!/usr/bin/env python3
"""
PagineGialle scraper — trova aziende italiane con email
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
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
BAD_EMAILS = ['esempio', 'example', 'test@', 'noreply', 'no-reply', 'info@pagine',
              'privacy@', 'dpo@', 'gdpr@', 'pec@', 'webmaster@', 'support@',
              'sentry', 'wixpress', '.png', '.jpg', '.gif']

def clean(s):
    return ' '.join(s.strip().split()) if s else ''

def is_good_email(email):
    e = email.lower()
    return not any(b in e for b in BAD_EMAILS)

def extract_emails_from_html(html):
    """Estrae email dal testo HTML, anche offuscate"""
    emails = set()

    # Email standard
    for e in EMAIL_RE.findall(html):
        if is_good_email(e):
            emails.add(e.lower())

    # Email offuscate: name [at] domain [dot] com
    obf = re.findall(r'[\w._%+\-]+\s*[\[\(]at[\]\)]\s*[\w.\-]+\s*[\[\(]dot[\]\)]\s*\w{2,}', html, re.I)
    for e in obf:
        cleaned = re.sub(r'\s*[\[\(]at[\]\)]\s*', '@', e, flags=re.I)
        cleaned = re.sub(r'\s*[\[\(]dot[\]\)]\s*', '.', cleaned, flags=re.I)
        if is_good_email(cleaned):
            emails.add(cleaned.lower())

    return list(emails)

def find_email_on_site(base_url):
    """Cerca email su homepage + pagine contatti"""
    if not base_url or not base_url.startswith('http'):
        return ''

    # Pagine da controllare
    paths_to_try = [
        '',           # homepage
        '/contatti',
        '/contattaci',
        '/contact',
        '/chi-siamo',
        '/about',
        '/info',
        '/dove-siamo',
    ]

    domain = urlparse(base_url).netloc.replace('www.', '')
    best_email = ''
    all_emails = []

    for path in paths_to_try:
        url = base_url.rstrip('/') + path if path else base_url
        try:
            r = requests.get(url, headers=HEADERS, timeout=8,
                           allow_redirects=True, verify=False)
            if r.status_code != 200:
                continue

            # Cerca mailto links prima (più affidabili)
            soup = BeautifulSoup(r.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
                email = a['href'].replace('mailto:', '').split('?')[0].strip().lower()
                if email and is_good_email(email):
                    # Email sul dominio del sito = oro
                    if domain in email:
                        return email
                    all_emails.append(email)

            # Poi cerca nel testo
            emails = extract_emails_from_html(r.text)
            for e in emails:
                if domain in e:
                    return e
                all_emails.append(e)

            if all_emails and path:  # trovata su pagina contatti
                break

        except Exception:
            pass

        time.sleep(random.uniform(0.5, 1.5))

    # Preferisci email sul dominio, poi prima trovata
    for e in all_emails:
        if domain in e:
            return e
    return all_emails[0] if all_emails else ''

def scrape_paginegialle(settore, citta, max_results=50):
    """Scrapa PagineGialle per settore e città"""
    results = []
    page = 1

    print(f"🔍 Cercando: {settore} a {citta}")

    while len(results) < max_results:
        query = settore.replace(' ', '+')
        location = citta.replace(' ', '+')
        url = f"https://www.paginegialle.it/ricerca/{query}/{location}/p-{page}"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  HTTP {resp.status_code} — stop")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Selettori PagineGialle (prova più varianti)
            cards = []

            # Variante 1: li con classe vcard o simile
            cards = soup.select('li.vcard, li[itemtype*="LocalBusiness"], li.item-list')

            # Variante 2: div con data-tracking o data-listing
            if not cards:
                cards = soup.select('div[data-tracking], div[data-listing-id], div[data-id]')

            # Variante 3: article
            if not cards:
                cards = soup.select('article.listing-item, article.result-item, article')

            # Variante 4: cerca per pattern di nome azienda
            if not cards:
                # Cerca tutte le h2/h3 che sembrano nomi aziende in un contesto di lista
                parent_set = set()
                for h in soup.find_all(['h2', 'h3']):
                    text = clean(h.get_text())
                    # Salta testi navigazione/UI
                    skip = ['ricerche correlate', 'risultati fuori', 'non hai trovato',
                           'cerca', 'filtri', 'ordina', 'mappa', 'elenco']
                    if any(s in text.lower() for s in skip):
                        continue
                    if len(text) > 3:
                        parent = h.parent.parent if h.parent else h.parent
                        if parent and id(parent) not in parent_set:
                            parent_set.add(id(parent))
                            cards.append(parent)

            if not cards:
                print(f"  Nessun risultato a pagina {page} — stop")
                break

            found_on_page = 0
            for card in cards:
                if len(results) >= max_results:
                    break

                try:
                    card_text = clean(card.get_text())

                    # Salta elementi di navigazione
                    skip_patterns = ['ricerche correlate', 'risultati fuori zona',
                                    'non hai trovato', 'cerca altri', 'mostra tutti']
                    if any(p in card_text.lower() for p in skip_patterns):
                        continue

                    # Nome azienda
                    nome = ''
                    for sel in ['h2', 'h3', '[itemprop="name"]', '.nome', '.tit', '.title']:
                        el = card.select_one(sel)
                        if el:
                            t = clean(el.get_text())
                            if t and len(t) > 2 and 'correlate' not in t.lower():
                                nome = t
                                break

                    if not nome or len(nome) < 3:
                        continue

                    # Indirizzo
                    indirizzo = citta
                    for sel in ['[itemprop="address"]', '.address', '.addr', '.indirizzo', '.via']:
                        el = card.select_one(sel)
                        if el:
                            indirizzo = clean(el.get_text()) or citta
                            break

                    # Telefono
                    telefono = ''
                    for a in card.find_all('a', href=re.compile(r'^tel:', re.I)):
                        telefono = a['href'].replace('tel:', '').strip()
                        break
                    if not telefono:
                        for sel in ['.phone', '.tel', '[itemprop="telephone"]']:
                            el = card.select_one(sel)
                            if el:
                                telefono = clean(el.get_text())
                                break

                    # Sito web
                    sito = ''
                    for a in card.find_all('a', href=True):
                        href = a['href']
                        if (href.startswith('http') and
                            'paginegialle' not in href and
                            'paginebianche' not in href and
                            not href.startswith('mailto:') and
                            not href.startswith('tel:')):
                            sito = href.rstrip('/')
                            break

                    # Email diretta (mailto nel card)
                    email = ''
                    for a in card.find_all('a', href=re.compile(r'^mailto:', re.I)):
                        e = a['href'].replace('mailto:', '').split('?')[0].strip().lower()
                        if e and is_good_email(e):
                            email = e
                            break

                    # URL dettaglio PagineGialle (per cercare email lì)
                    pg_detail = ''
                    for a in card.find_all('a', href=True):
                        href = a['href']
                        if 'paginegialle.it' in href and '/ricerca/' not in href:
                            pg_detail = href
                            break

                    result = {
                        'nome': nome,
                        'settore': settore,
                        'citta': citta,
                        'indirizzo': indirizzo,
                        'telefono': telefono,
                        'sito': sito,
                        'pg_detail': pg_detail,
                        'email': email,
                        'email_trovata': bool(email),
                        'scraped_at': datetime.now().isoformat()
                    }
                    results.append(result)
                    found_on_page += 1
                    status = '✉️' if email else '🌐' if sito else '📞' if telefono else '📋'
                    print(f"  {status} {nome} | {indirizzo[:40]}")

                except Exception:
                    continue

            if found_on_page == 0:
                print(f"  0 listing validi a pagina {page} — stop")
                break

            page += 1
            time.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"  Errore pagina {page}: {e}")
            break

    return results

def find_missing_emails(results):
    """Per aziende senza email, cerca su sito web e pagina dettaglio PG"""
    no_email = [r for r in results if not r['email']]
    con_sito = [r for r in no_email if r.get('sito')]
    con_pg = [r for r in no_email if not r.get('sito') and r.get('pg_detail')]

    print(f"\n📧 Cerco email: {len(con_sito)} con sito, {len(con_pg)} solo PagineGialle...")

    # Prima prova dal sito web (più ricco di info)
    for r in con_sito:
        print(f"  🔎 {r['nome']} ({r['sito'][:50]})")
        email = find_email_on_site(r['sito'])
        if email:
            r['email'] = email
            r['email_trovata'] = True
            print(f"     ✅ {email}")
        else:
            print(f"     ❌ non trovata")
        time.sleep(random.uniform(1, 2))

    # Poi prova dalla pagina dettaglio PagineGialle
    for r in con_pg:
        try:
            url = r['pg_detail']
            if not url.startswith('http'):
                url = 'https://www.paginegialle.it' + url
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Cerca mailto nel dettaglio
            for a in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
                e = a['href'].replace('mailto:', '').split('?')[0].strip().lower()
                if e and is_good_email(e):
                    r['email'] = e
                    r['email_trovata'] = True
                    print(f"  ✅ PG detail: {r['nome']} → {e}")
                    break

            # Se c'è sito web nel dettaglio, aggiorna
            if not r['sito']:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if href.startswith('http') and 'paginegialle' not in href:
                        r['sito'] = href.rstrip('/')
                        break

        except Exception:
            pass
        time.sleep(random.uniform(1, 2))

    return results

def save_results(results, settore, citta):
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    base = f"data/prospect_{settore.replace(' ','_')}_{citta.replace(' ','_')}_{timestamp}"

    with open(f"{base}.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(f"{base}.csv", 'w', encoding='utf-8') as f:
        f.write("Nome,Settore,Città,Email,Telefono,Sito\n")
        for r in results:
            f.write(f'"{r["nome"]}","{r["settore"]}","{r["citta"]}","{r.get("email","")}","{r.get("telefono","")}","{r.get("sito","")}"\n')

    con_email = sum(1 for r in results if r.get('email'))
    print(f"\n✅ Salvati {len(results)} prospect ({con_email} con email)")
    print(f"   📄 {base}.json")
    print(f"   📊 {base}.csv")
    return base

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    parser = argparse.ArgumentParser()
    parser.add_argument('--settore', default='ristoranti', help='Settore')
    parser.add_argument('--citta', default='Milano', help='Città')
    parser.add_argument('--n', type=int, default=50, help='Numero massimo risultati')
    parser.add_argument('--no-email-search', action='store_true')
    args = parser.parse_args()

    results = scrape_paginegialle(args.settore, args.citta, args.n)

    if results and not args.no_email_search:
        results = find_missing_emails(results)

    save_results(results, args.settore, args.citta)
