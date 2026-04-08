#!/usr/bin/env python3
"""
Creative Mess ADV — PagineGialle Scraper
Raccoglie aziende italiane con email per settore e città.
Uso: python paginegialle.py --settore "ristoranti" --citta "Milano" --pagine 10

Output: CSV pronto per import in Instantly.ai / Brevo / Apollo
"""

import argparse
import csv
import os
import re
import time
import random
import requests
from datetime import datetime
from urllib.parse import quote, urljoin, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")  # Imposta HUNTER_API_KEY nell'ambiente


def pg_search_url(settore: str, citta: str, pagina: int = 1) -> str:
    s = quote(settore.strip())
    c = quote(citta.strip())
    return f"https://www.paginegialle.it/ricerca/{s}/{c}/p-{pagina}"


def extract_emails_from_text(text: str) -> list[str]:
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    found = re.findall(pattern, text)
    # Filtra email di sistema / placeholder
    blacklist = {"example.com", "domain.com", "email.com", "mail.com", "sito.it", "noreply"}
    return [e.lower() for e in found if not any(b in e.lower() for b in blacklist)]


def extract_emails_from_website(url: str, timeout: int = 6) -> list[str]:
    """Scarica la homepage del sito e cerca email nel testo."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.ok:
            emails = extract_emails_from_text(r.text)
            if not emails:
                # Prova anche la pagina /contatti o /contattaci
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                for path in ["/contatti", "/contattaci", "/contact", "/chi-siamo"]:
                    try:
                        r2 = requests.get(base + path, headers=HEADERS, timeout=4)
                        if r2.ok:
                            emails = extract_emails_from_text(r2.text)
                            if emails:
                                break
                    except Exception:
                        pass
            return emails
    except Exception:
        pass
    return []


def hunter_find_email(domain: str) -> str:
    """Usa Hunter.io per trovare email dal dominio (richiede API key)."""
    if not HUNTER_API_KEY:
        return ""
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": HUNTER_API_KEY, "limit": 1},
            timeout=8,
        )
        if r.ok:
            data = r.json()
            emails = data.get("data", {}).get("emails", [])
            if emails:
                return emails[0].get("value", "")
    except Exception:
        pass
    return ""


def scrape_paginegialle(settore: str, citta: str, n_pagine: int = 5) -> list[dict]:
    """Scarica le pagine di PagineGialle e restituisce lista aziende."""
    risultati = []
    seen_names = set()

    for pagina in range(1, n_pagine + 1):
        url = pg_search_url(settore, citta, pagina)
        print(f"  → Pagina {pagina}: {url}")

        try:
            r = requests.get(url, headers=HEADERS, timeout=12)
            if not r.ok:
                print(f"    ✗ HTTP {r.status_code} — stop")
                break
        except Exception as e:
            print(f"    ✗ Errore connessione: {e}")
            break

        html = r.text

        # Estrai blocchi azienda con regex (più robusto di BeautifulSoup senza dipendenze extra)
        # Pattern per nome azienda
        nomi = re.findall(
            r'class="[^"]*(?:title|name|heading|denominazione)[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{3,80})',
            html, re.IGNORECASE
        )
        # Pattern alternativo per h2/h3 con link
        if not nomi:
            nomi = re.findall(r'<h[23][^>]*>\s*<a[^>]*>([^<]{3,80})</a>', html)

        # Estrai siti web
        siti = re.findall(
            r'href="(https?://(?!(?:www\.paginegialle|facebook|instagram|twitter|linkedin))[^"]{5,100})"[^>]*>[^<]*sito|visitа',
            html, re.IGNORECASE
        )
        # Pattern più generico per URL esterni
        tutti_link = re.findall(r'href="(https?://[^"]{10,100})"', html)
        siti_esterni = [
            l for l in tutti_link
            if "paginegialle" not in l and "google" not in l
            and "facebook" not in l and "instagram" not in l
            and "twitter" not in l and "linkedin" not in l
            and "whatsapp" not in l and "mailto" not in l
        ]

        # Email dirette nella pagina
        email_in_pagina = extract_emails_from_text(html)

        # Telefoni
        telefoni = re.findall(r'\b(?:0\d{1,4}[\s\-]?\d{5,8}|[3][0-9]{9})\b', html)

        # Costruisci risultati per questa pagina
        n_trovati_pagina = max(len(nomi), 5)
        for i in range(min(n_trovati_pagina, 20)):
            nome = nomi[i].strip() if i < len(nomi) else f"Azienda {i+1}"
            nome = re.sub(r'\s+', ' ', nome).strip()

            if not nome or nome in seen_names or len(nome) < 3:
                continue
            seen_names.add(nome)

            sito = siti_esterni[i] if i < len(siti_esterni) else ""
            telefono = telefoni[i] if i < len(telefoni) else ""
            email_diretta = email_in_pagina[i] if i < len(email_in_pagina) else ""

            risultati.append({
                "nome": nome,
                "settore": settore,
                "citta": citta,
                "telefono": telefono,
                "sito_web": sito,
                "email": email_diretta,
                "fonte": "PagineGialle",
            })

        # Pausa casuale per non stressare il server
        time.sleep(random.uniform(1.5, 3.5))

    return risultati


def arricchisci_email(aziende: list[dict], max_richieste: int = 200) -> list[dict]:
    """Per le aziende senza email, cerca l'email dal sito o con Hunter."""
    n = 0
    for az in aziende:
        if az["email"]:
            continue
        if n >= max_richieste:
            break

        sito = az.get("sito_web", "")
        if sito:
            print(f"  🔍 Cerco email su: {sito}")
            emails = extract_emails_from_website(sito)
            if emails:
                az["email"] = emails[0]
                print(f"     ✓ Trovata: {emails[0]}")
            elif HUNTER_API_KEY:
                dominio = urlparse(sito).netloc.replace("www.", "")
                email_hunter = hunter_find_email(dominio)
                if email_hunter:
                    az["email"] = email_hunter
                    az["fonte"] += " + Hunter"
                    print(f"     ✓ Hunter: {email_hunter}")
            n += 1
            time.sleep(random.uniform(0.5, 1.5))

    return aziende


def salva_csv(aziende: list[dict], output: str):
    """Salva i risultati in CSV compatibile con Instantly.ai / Brevo."""
    if not aziende:
        print("Nessuna azienda trovata.")
        return

    with open(output, "w", newline="", encoding="utf-8") as f:
        campi = ["nome", "email", "telefono", "sito_web", "settore", "citta", "fonte"]
        writer = csv.DictWriter(f, fieldnames=campi)
        writer.writeheader()
        for az in aziende:
            writer.writerow({k: az.get(k, "") for k in campi})

    con_email = sum(1 for a in aziende if a["email"])
    print(f"\n✅ Salvato: {output}")
    print(f"   Totale aziende: {len(aziende)}")
    print(f"   Con email:      {con_email} ({con_email*100//len(aziende) if aziende else 0}%)")
    print(f"   Senza email:    {len(aziende) - con_email}")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper PagineGialle per Creative Mess ADV"
    )
    parser.add_argument("--settore", required=True, help='Es: "ristoranti", "dentisti", "avvocati"')
    parser.add_argument("--citta", required=True, help='Es: "Milano", "Roma", "Napoli"')
    parser.add_argument("--pagine", type=int, default=5, help="Numero di pagine da scansionare (default: 5)")
    parser.add_argument("--output", default="", help="Nome file CSV output (default: auto)")
    parser.add_argument("--no-arricchimento", action="store_true",
                        help="Salta la ricerca email sui siti web")
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output = args.output or f"prospect_{args.settore.replace(' ','_')}_{args.citta}_{timestamp}.csv"

    print(f"\n🔍 Creative Mess ADV — Scraper PagineGialle")
    print(f"   Settore: {args.settore}")
    print(f"   Città:   {args.citta}")
    print(f"   Pagine:  {args.pagine}")
    print(f"   Output:  {output}\n")

    print("📥 Raccolta aziende da PagineGialle...")
    aziende = scrape_paginegialle(args.settore, args.citta, args.pagine)
    print(f"   → {len(aziende)} aziende trovate\n")

    if not args.no_arricchimento:
        print("📧 Ricerca email sui siti web...")
        aziende = arricchisci_email(aziende)

    salva_csv(aziende, output)

    print("\n📋 Anteprima prime 5 righe:")
    for az in aziende[:5]:
        print(f"   • {az['nome']} | {az['email'] or 'NO EMAIL'} | {az['sito_web'] or 'no sito'}")


if __name__ == "__main__":
    main()
