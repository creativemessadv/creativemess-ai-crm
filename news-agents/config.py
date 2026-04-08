"""
Configurazione centrale per il sistema di news agents.
Modifica questo file per personalizzare fonti, orari e destinatari.
"""

# ─── FONTI RSS ──────────────────────────────────────────────────────────────

WEB_MARKETING_FEEDS = [
    {"name": "Search Engine Journal", "url": "https://www.searchenginejournal.com/feed/"},
    {"name": "HubSpot Blog",          "url": "https://blog.hubspot.com/marketing/rss.xml"},
    {"name": "Moz Blog",              "url": "https://moz.com/blog/feed"},
    {"name": "Neil Patel",            "url": "https://neilpatel.com/blog/feed/"},
    {"name": "Social Media Examiner", "url": "https://www.socialmediaexaminer.com/feed/"},
    {"name": "MarTech",               "url": "https://martech.org/feed/"},
    {"name": "Content Mktg Institute","url": "https://contentmarketinginstitute.com/feed/"},
    {"name": "Search Engine Land",    "url": "https://searchengineland.com/feed"},
]

AI_FEEDS = [
    {"name": "TechCrunch AI",         "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    {"name": "VentureBeat AI",        "url": "https://venturebeat.com/category/ai/feed/"},
    {"name": "MIT Tech Review",       "url": "https://www.technologyreview.com/feed/"},
    {"name": "Anthropic Blog",        "url": "https://www.anthropic.com/rss.xml"},
    {"name": "Hacker News AI",        "url": "https://hnrss.org/frontpage?q=AI+LLM+machine+learning"},
    {"name": "The Verge AI",          "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
    {"name": "InfoQ AI/ML",           "url": "https://www.infoq.com/ai-ml-data-eng/rss/"},
]

# ─── IMPOSTAZIONI EMAIL ──────────────────────────────────────────────────────

EMAIL_CONFIG = {
    "smtp_host": "smtp.zoho.eu",   # oppure smtp.zoho.com se il tuo account non è .eu
    "smtp_port": 587,
    # Impostati via variabili d'ambiente nel file .env
    # EMAIL_USER=tua@zoho.com  (o tua@creativemessadv.it se dominio custom su Zoho)
    # EMAIL_PASSWORD=la-tua-password-zoho
    # EMAIL_RECIPIENT=roberto@creativemessadv.it
}

# ─── SCHEDULER ───────────────────────────────────────────────────────────────

SEND_TIME = "08:00"          # Orario di invio email (formato HH:MM)
FETCH_INTERVAL_HOURS = 2     # Ogni quante ore raccogliere nuove notizie
MAX_ARTICLES_PER_FEED = 10   # Max articoli per feed da considerare
LOOKBACK_HOURS = 26          # Quante ore indietro guardare per le notizie

# ─── CURAZIONE AI ────────────────────────────────────────────────────────────

TOP_N_ARTICLES = 7           # Quanti articoli selezionare per ogni email
CLAUDE_MODEL = "claude-opus-4-6"
