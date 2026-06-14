# =====================================================================
#  config.py - Configurazione centrale del modulo Pokémon TCG
# ---------------------------------------------------------------------
#  Qui si trovano tutti i "parametri" del sistema in un unico posto:
#  chiavi API, percorsi dei file, e soprattutto la LISTA delle cose
#  che vogliamo monitorare (set di carte e parole chiave).
#
#  Modifica liberamente le liste qui sotto: NON serve toccare il resto
#  del codice per cambiare cosa viene monitorato.
# =====================================================================

import os
from pathlib import Path

from dotenv import load_dotenv

# Cartella in cui si trova questo file (la base del modulo).
BASE_DIR = Path(__file__).resolve().parent

# Carica le variabili dal file .env (chiavi API, ecc.).
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------
# CHIAVI API (lette dal file .env)
# ---------------------------------------------------------------------
# Chiave gratuita di pokemontcg.io. Può essere vuota (funziona comunque).
POKEMONTCG_API_KEY = os.getenv("POKEMONTCG_API_KEY", "").strip()

# ---------------------------------------------------------------------
# PERCORSI DEI FILE
# ---------------------------------------------------------------------
# Database SQLite locale dove salviamo prezzi, trend e carte calde.
DB_PATH = BASE_DIR / "pokemon_tcg.db"

# Cartella dove salviamo i report giornalieri in formato markdown.
REPORT_DIR = BASE_DIR / "report"

# ---------------------------------------------------------------------
# COSA MONITORARE: SET DI CARTE
# ---------------------------------------------------------------------
# Ogni set ha un "id" usato dall'API pokemontcg.io. Esempi recenti:
#   sv8   = Surging Sparks         sv7  = Stellar Crown
#   sv6pt5 = Shrouded Fable        sv6  = Twilight Masquerade
#   sv5   = Temporal Forces        sv4pt5 = Paldean Fates
#   sv4   = Paradox Rift           sv3pt5 = 151
# Per scoprire altri id: https://api.pokemontcg.io/v2/sets
#
# Suggerimento: monitora pochi set "caldi" alla volta (3-6) per restare
# leggero e dentro i limiti dell'API gratuita.
SET_DA_MONITORARE = [
    "sv8",      # Surging Sparks
    "sv7",      # Stellar Crown
    "sv6pt5",   # Shrouded Fable
    "sv3pt5",   # 151 (molto richiesto)
]

# Numero massimo di carte da scaricare per ogni set (le più "pesanti"
# per prezzo vengono comunque tutte considerate dall'analisi).
MAX_CARTE_PER_SET = 250

# Prezzo minimo (in valuta della fonte) sotto al quale ignoriamo una
# carta nell'analisi "carte calde": serve a togliere il rumore delle
# carte comuni da pochi centesimi.
PREZZO_MINIMO_ANALISI = 1.0

# Quante carte calde segnalare ogni giorno (l'obiettivo era 3-5).
NUMERO_CARTE_CALDE = 5

# ---------------------------------------------------------------------
# COSA MONITORARE: PAROLE CHIAVE PER GOOGLE TRENDS
# ---------------------------------------------------------------------
# Massimo 5 parole chiave per chiamata (limite di Google Trends).
KEYWORD_TRENDS = [
    "Pokemon TCG",
    "Pokemon cards",
    "Surging Sparks",
    "Pokemon 151",
    "Charizard card",
]

# Area geografica per Google Trends ("" = mondo, "IT" = Italia,
# "US" = Stati Uniti). Per la rivendita italiana puoi mettere "IT".
TRENDS_PAESE = ""

# Finestra temporale di Google Trends (formato della libreria pytrends).
# "now 7-d" = ultimi 7 giorni; "today 3-m" = ultimi 3 mesi.
TRENDS_PERIODO = "now 7-d"
