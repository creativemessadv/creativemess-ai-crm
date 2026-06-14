# Pokémon TCG — Sistema semi-automatizzato per Instagram

Sistema modulare e a budget (quasi) zero per gestire un account Instagram
di rivendita di carte e prodotti Pokémon (TCG). Costruito a step.

> **Stato attuale:** ✅ Step 1 (Modulo Trend) completo.
> Prossimi: Step 2 (generazione contenuti con Claude), Step 3 (programmazione
> Instagram), Step 4 (dashboard).

---

## Architettura

| Step | Modulo | Cosa fa | Stato |
|------|--------|---------|-------|
| 1 | **Trend** | Legge prezzi TCG + Google Trends, salva su SQLite, segnala le carte "calde" | ✅ Fatto |
| 2 | Contenuti | Genera con Claude script Reel, caption, hashtag, idee carosello | ⏳ Da fare |
| 3 | Programmazione | Mette in coda post-immagine/caroselli via Instagram Graph API | ⏳ Da fare |
| 4 | Dashboard | Pagina locale Flask con trend, bozze e coda | ⏳ Da fare |

---

## Step 1 — Modulo Trend

### Fonti dati e perché (rispetto dei Terms of Service)

- **Prezzi → [pokemontcg.io](https://dev.pokemontcg.io/)**: API **gratuita e
  legale** che aggrega i prezzi di **TCGplayer** e **Cardmarket**. Usandola
  **non facciamo scraping**, quindi non violiamo i ToS di nessuno.
- **Google Trends → `pytrends`**: nessuna API ufficiale esiste; pytrends usa
  l'endpoint interno. Va bene per **uso personale a basso volume**. Se viene
  bloccato, il sistema continua comunque (salta solo i Trends). In alternativa
  puoi esportare i CSV manualmente da
  [trends.google.it](https://trends.google.it/trends/explore).

Fonti **scartate** perché a pagamento o vietate dai ToS: PriceCharting
(API a pagamento, scraping vietato), Cardmarket diretto (richiede account
venditore + OAuth), TCGplayer (API chiusa ai nuovi sviluppatori).

### Cosa ti devi procurare (gratis)

1. **Chiave API pokemontcg.io** (consigliata, opzionale):
   registrati su <https://dev.pokemontcg.io/>, copia la API key.
   Senza chiave funziona lo stesso ma con limiti più bassi.

### Installazione (macOS)

```bash
cd pokemon-tcg

# 1) Ambiente virtuale Python (consigliato, tiene tutto isolato)
python3 -m venv .venv
source .venv/bin/activate

# 2) Dipendenze
pip install -r requirements.txt

# 3) Configurazione chiavi
cp .env.example .env
# poi apri .env e incolla la tua POKEMONTCG_API_KEY (facoltativa)
```

### Uso

```bash
python3 step1_trend.py
```

Cosa succede:
1. crea/apre il database `pokemon_tcg.db`;
2. scarica i prezzi dei set elencati in `config.py` (`SET_DA_MONITORARE`);
3. scarica l'interesse Google Trends per le parole chiave (`KEYWORD_TRENDS`);
4. individua le **3-5 carte calde** del giorno;
5. scrive un report leggibile in `report/trend_AAAA-MM-GG.md`.

> ⚠️ **Al primo avvio** non c'è ancora storico, quindi i confronti
> giorno-su-giorno non sono possibili: vedrai segnali solo dal "momentum"
> di Cardmarket. Dal **secondo giorno** in poi il confronto diventa pieno.
> **Lancialo una volta al giorno** per costruire lo storico.

### Automazione giornaliera (opzionale, macOS)

Per lanciarlo ogni giorno alle 9:00 con `cron`:

```bash
crontab -e
# aggiungi questa riga (adatta il percorso assoluto):
0 9 * * * cd /percorso/assoluto/pokemon-tcg && ./.venv/bin/python step1_trend.py
```

### Struttura dei file

```
pokemon-tcg/
├── config.py          # tutti i parametri: chiavi, set e keyword da monitorare
├── database.py        # gestione SQLite (lettura/scrittura)
├── fonte_prezzi.py    # client API pokemontcg.io (prezzi)
├── fonte_trends.py    # client Google Trends (pytrends)
├── analisi_trend.py   # logica che individua le "carte calde"
├── step1_trend.py     # script principale da lanciare ogni giorno
├── requirements.txt   # dipendenze Python
├── .env.example       # modello per le chiavi (copialo in .env)
└── report/            # report markdown giornalieri (generati a runtime)
```

### Come personalizzare

Apri `config.py`:
- **`SET_DA_MONITORARE`**: gli ID dei set da seguire
  (lista completa: <https://api.pokemontcg.io/v2/sets>).
- **`KEYWORD_TRENDS`**: le parole chiave per Google Trends (max 5).
- **`TRENDS_PAESE`**: `""` mondo, `"IT"` Italia.
- **`NUMERO_CARTE_CALDE`**: quante carte segnalare (default 5).
