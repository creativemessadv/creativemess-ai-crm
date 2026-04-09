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

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'it-IT,it;q=0.9',
}

def clean(s):
    return s.strip() if s else ''

def extract_email_from_site(url):
    """Prova a trovare email dal sito web dell'azienda"""
    if not url or not url.startswith('http'):
        return ''
    try:
        r = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
        emails = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', r.text)
        # Filtra email generiche/spam
        bad = ['esempio', 'example', 'test', 'noreply', 'no-reply', 'info@pagine', 'privacy']
        emails = [e.lower() for e in emails if not any(b in e.lower() for b in bad)]
        # Preferisci email con dominio uguale al sito
        domain = url.split('/')[2].replace('www.', '')
        for e in emails:
            if domain in e:
                return e
        return emails[0] if emails else ''
    except:
        return ''

def scrape_paginegialle(settore, citta, max_results=50):
    """Scrapa PagineGialle per settore e città"""
    results = []
    page = 1
    
    print(f"🔍 Cercando: {settore} a {citta}")
    
    while len(results) < max_results:
        # URL PagineGialle
        query = settore.replace(' ', '+')
        location = citta.replace(' ', '+')
        url = f"https://www.paginegialle.it/ricerca/{query}/{location}/p-{page}"
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  Status {resp.status_code} — stop")
                break
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Cerca le schede aziende
            cards = soup.find_all('div', class_=re.compile(r'card|listing|result', re.I))
            if not cards:
                # Prova selettore alternativo
                cards = soup.find_all('article')
            
            if not cards:
                print(f"  Nessun risultato a pagina {page}")
                break
            
            for card in cards:
                if len(results) >= max_results:
                    break
                
                try:
                    # Nome azienda
                    nome_el = card.find(['h2', 'h3', 'a'], class_=re.compile(r'name|title|company', re.I))
                    nome = clean(nome_el.get_text()) if nome_el else ''
                    if not nome:
                        continue
                    
                    # Indirizzo/città
                    addr_el = card.find(class_=re.compile(r'address|addr|location', re.I))
                    indirizzo = clean(addr_el.get_text()) if addr_el else citta
                    
                    # Telefono
                    tel_el = card.find(class_=re.compile(r'phone|tel', re.I))
                    telefono = clean(tel_el.get_text()) if tel_el else ''
                    
                    # Sito web
                    sito = ''
                    for link in card.find_all('a', href=True):
                        href = link['href']
                        if href.startswith('http') and 'paginegialle' not in href:
                            sito = href
                            break
                    
                    # Email (diretta o da sito)
                    email = ''
                    email_el = card.find('a', href=re.compile(r'mailto:', re.I))
                    if email_el:
                        email = email_el['href'].replace('mailto:', '').split('?')[0]
                    
                    result = {
                        'nome': nome,
                        'settore': settore,
                        'citta': citta,
                        'indirizzo': indirizzo,
                        'telefono': clean(telefono.replace('Telefono:', '')),
                        'sito': sito,
                        'email': email,
                        'email_trovata': bool(email),
                        'scraped_at': datetime.now().isoformat()
                    }
                    results.append(result)
                    status = '✉️' if email else '🌐' if sito else '📞'
                    print(f"  {status} {nome} | {indirizzo}")
                    
                except Exception as e:
                    continue
            
            page += 1
            time.sleep(random.uniform(2, 4))  # rispetta il sito
            
        except Exception as e:
            print(f"  Errore pagina {page}: {e}")
            break
    
    return results

def find_missing_emails(results):
    """Per aziende senza email, prova a trovarla dal sito web"""
    no_email = [r for r in results if not r['email'] and r['sito']]
    print(f"\n📧 Cerco email per {len(no_email)} aziende con sito web...")
    
    for r in no_email:
        email = extract_email_from_site(r['sito'])
        if email:
            r['email'] = email
            r['email_trovata'] = True
            print(f"  ✅ Trovata: {r['nome']} → {email}")
        time.sleep(random.uniform(1, 2))
    
    return results

def save_results(results, settore, citta):
    """Salva risultati in JSON e CSV"""
    os.makedirs('data', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    base = f"data/prospect_{settore.replace(' ','_')}_{citta.replace(' ','_')}_{timestamp}"
    
    # JSON completo
    with open(f"{base}.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # CSV semplice
    with open(f"{base}.csv", 'w', encoding='utf-8') as f:
        f.write("Nome,Settore,Città,Email,Telefono,Sito\n")
        for r in results:
            f.write(f'"{r["nome"]}","{r["settore"]}","{r["citta"]}","{r["email"]}","{r["telefono"]}","{r["sito"]}"\n')
    
    con_email = sum(1 for r in results if r['email'])
    print(f"\n✅ Salvati {len(results)} prospect ({con_email} con email)")
    print(f"   📄 {base}.json")
    print(f"   📊 {base}.csv")
    return base

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--settore', default='ristoranti', help='Settore (es. ristoranti, dentisti, avvocati)')
    parser.add_argument('--citta', default='Milano', help='Città')
    parser.add_argument('--n', type=int, default=50, help='Numero massimo risultati')
    parser.add_argument('--no-email-search', action='store_true', help='Non cercare email dai siti')
    args = parser.parse_args()
    
    results = scrape_paginegialle(args.settore, args.citta, args.n)
    
    if not args.no_email_search:
        results = find_missing_emails(results)
    
    save_results(results, args.settore, args.citta)
