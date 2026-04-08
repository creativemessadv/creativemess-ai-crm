# Scraper PagineGialle — Creative Mess ADV

Raccoglie aziende italiane per settore e città, trova le email.

## Setup

```bash
cd scraper
pip install requests
```

## Utilizzo

```bash
# Ristoranti a Milano (5 pagine = ~100 aziende)
python paginegialle.py --settore "ristoranti" --citta "Milano" --pagine 5

# Dentisti a Roma
python paginegialle.py --settore "dentisti" --citta "Roma" --pagine 10

# Avvocati a Torino con Hunter.io
HUNTER_API_KEY=la-tua-chiave python paginegialle.py --settore "avvocati" --citta "Torino"

# Solo raccolta, senza cercare email sui siti
python paginegialle.py --settore "hotel" --citta "Firenze" --no-arricchimento
```

## Output CSV

Compatibile con **Instantly.ai**, **Brevo**, **Mailchimp**, **Apollo**.

Colonne: `nome, email, telefono, sito_web, settore, citta, fonte`

## Settori consigliati (alto potenziale)

- `ristoranti` — siti spesso vecchi, no SEO
- `dentisti` — alto valore cliente, budget disponibile
- `avvocati` — cercano visibilità online
- `hotel` — dipendono da booking.com, vogliono indipendenza
- `estetiste` — social media fondamentale
- `officine meccaniche` — spesso senza presenza online
- `immobiliari` — cercano SEO locale
- `commercialisti` — pubblico professionale, LinkedIn

## Hunter.io (opzionale)

Per trovare email dai domini senza email pubblica:
1. Registrati su hunter.io
2. Ottieni API key gratuita (25 ricerche/mese)
3. `export HUNTER_API_KEY=la-tua-chiave`
