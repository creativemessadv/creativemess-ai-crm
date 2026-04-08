"""
Orchestratore principale del sistema News Agents.

Modalità di utilizzo:
  python main.py              → avvia lo scheduler (gira 24/7)
  python main.py --now        → esegui subito e poi esci
  python main.py --fetch-only → solo fetch, nessuna email
  python main.py --test       → test email con 3 articoli di esempio
"""

import os
import sys
import logging
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

# Carica .env prima di tutto il resto
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import fetcher
import curator
import mailer
from config import SEND_TIME, FETCH_INTERVAL_HOURS

# ─── LOGGING ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "cache", "agent.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("main")


# ─── JOBS ────────────────────────────────────────────────────────────────────

def job_fetch():
    """Job periodico: scarica nuovi articoli da tutti i feed RSS."""
    logger.info("▶ JOB FETCH avviato")
    try:
        fetcher.fetch_all()
        logger.info("✅ Fetch completato")
    except Exception as e:
        logger.error(f"❌ Errore nel job fetch: {e}", exc_info=True)


def job_send_digest():
    """Job mattutino: cura e invia le due email di digest."""
    logger.info("▶ JOB DIGEST avviato")

    # Prima aggiorna le notizie
    job_fetch()

    articles = fetcher.load_cached()

    wm_articles = articles.get("web_marketing", [])
    ai_articles = articles.get("ai", [])

    if not wm_articles and not ai_articles:
        logger.warning("⚠️  Nessun articolo in cache, digest non inviato")
        return

    # Cura con Claude
    logger.info("Curazione Web Marketing...")
    curated_wm = curator.curate("web_marketing", wm_articles)

    logger.info("Curazione AI...")
    curated_ai = curator.curate("ai", ai_articles)

    # Invia le email
    ok_wm = mailer.send_email("web_marketing", curated_wm)
    ok_ai = mailer.send_email("ai", curated_ai)

    if ok_wm or ok_ai:
        # Segna come inviati solo se almeno un'email è andata a buon fine
        sent_wm = [a for a in wm_articles
                   if any(s["url"] == a["link"] for s in curated_wm.get("selected", []))]
        sent_ai = [a for a in ai_articles
                   if any(s["url"] == a["link"] for s in curated_ai.get("selected", []))]
        fetcher.mark_as_sent(sent_wm, sent_ai)

    logger.info(
        f"✅ Digest completato → WM: {'OK' if ok_wm else 'FAIL'}, "
        f"AI: {'OK' if ok_ai else 'FAIL'}"
    )


def _check_env():
    """Controlla che le variabili d'ambiente essenziali siano presenti."""
    missing = []
    for var in ["ANTHROPIC_API_KEY", "EMAIL_USER", "EMAIL_PASSWORD"]:
        if not os.environ.get(var):
            missing.append(var)
    if missing:
        logger.error(f"Variabili d'ambiente mancanti: {', '.join(missing)}")
        logger.error("Copia .env.example in .env e compila i valori")
        sys.exit(1)


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # Assicura che la cartella cache esista
    os.makedirs(os.path.join(os.path.dirname(__file__), "cache"), exist_ok=True)

    if "--test" in args:
        # Modalità test: invia email con articoli fittizi
        logger.info("🧪 Modalità TEST")
        _check_env()
        test_curated = {
            "selected": [
                {
                    "rank": 1,
                    "title": "Come l'AI sta trasformando il SEO nel 2025",
                    "source": "Search Engine Journal",
                    "url": "https://www.searchenginejournal.com",
                    "published": datetime.now().strftime("%Y-%m-%d"),
                    "why_important": "Google sta integrando modelli AI nei risultati di ricerca. Questo cambierà le strategie SEO radicalmente.",
                    "key_takeaway": "Inizia a ottimizzare i contenuti per l'AI overview di Google.",
                },
                {
                    "rank": 2,
                    "title": "Meta lancia nuovi strumenti AI per gli advertiser",
                    "source": "Social Media Examiner",
                    "url": "https://www.socialmediaexaminer.com",
                    "published": datetime.now().strftime("%Y-%m-%d"),
                    "why_important": "Meta Advantage+ ora usa il machine learning per ottimizzare automaticamente le creatività degli annunci.",
                    "key_takeaway": "Testa le campagne AI-driven per i tuoi clienti e-commerce.",
                },
            ],
            "category_insight": "Il web marketing sta vivendo una rivoluzione AI: chi si adatta ora avrà vantaggio competitivo nei prossimi 12 mesi.",
        }
        mailer.send_email("web_marketing", test_curated)
        mailer.send_email("ai", test_curated)
        return

    if "--fetch-only" in args:
        logger.info("🔄 Solo fetch, nessuna email")
        fetcher.fetch_all()
        return

    _check_env()

    if "--now" in args:
        logger.info("⚡ Esecuzione immediata del digest")
        job_send_digest()
        return

    # ─── MODALITÀ SCHEDULER 24/7 ──────────────────────────────────────────
    logger.info("🚀 News Agents avviati in modalità scheduler")
    logger.info(f"   Email giornaliera: {SEND_TIME}")
    logger.info(f"   Fetch ogni: {FETCH_INTERVAL_HOURS}h")

    # Fetch iniziale al boot
    job_fetch()

    # Schedula fetch periodico
    schedule.every(FETCH_INTERVAL_HOURS).hours.do(job_fetch)

    # Schedula digest mattutino
    schedule.every().day.at(SEND_TIME).do(job_send_digest)

    logger.info(f"⏰ Prossimo digest: {SEND_TIME} ogni giorno")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
