"""
Agente Fetcher: raccoglie articoli da feed RSS e li normalizza.
Gira in background ogni FETCH_INTERVAL_HOURS ore.
"""

import feedparser
import logging
import json
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict
from config import WEB_MARKETING_FEEDS, AI_FEEDS, MAX_ARTICLES_PER_FEED, LOOKBACK_HOURS

logger = logging.getLogger(__name__)

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache", "articles.json")
SENT_FILE  = os.path.join(os.path.dirname(__file__), "cache", "sent_ids.json")


def _ensure_cache_dir():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)


def _load_json(path: str, default):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _save_json(path: str, data):
    _ensure_cache_dir()
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _parse_entry(entry: dict, source_name: str) -> Dict | None:
    """Converte un entry feedparser in un dizionario normalizzato."""
    # Data pubblicazione
    published = None
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                published = datetime(*t[:6], tzinfo=timezone.utc)
                break
            except Exception:
                pass
    if not published:
        published = datetime.now(timezone.utc)

    # Filtra articoli troppo vecchi
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    if published < cutoff:
        return None

    # Summary: prendi il testo pulito
    summary = ""
    if hasattr(entry, "summary"):
        import re
        summary = re.sub(r"<[^>]+>", "", entry.summary or "").strip()
    summary = summary[:500] if summary else ""

    return {
        "id":        entry.get("id") or entry.get("link", ""),
        "title":     entry.get("title", "").strip(),
        "link":      entry.get("link", ""),
        "summary":   summary,
        "source":    source_name,
        "published": published.isoformat(),
    }


def fetch_feed(feed_cfg: Dict) -> List[Dict]:
    """Scarica e parsa un singolo feed RSS."""
    articles = []
    try:
        logger.info(f"Fetching: {feed_cfg['name']}")
        parsed = feedparser.parse(feed_cfg["url"])
        for entry in parsed.entries[:MAX_ARTICLES_PER_FEED]:
            article = _parse_entry(entry, feed_cfg["name"])
            if article and article["title"] and article["link"]:
                articles.append(article)
    except Exception as e:
        logger.warning(f"Errore fetch {feed_cfg['name']}: {e}")
    return articles


def fetch_all() -> Dict[str, List[Dict]]:
    """
    Scarica tutti i feed RSS.
    Ritorna: {"web_marketing": [...], "ai": [...]}
    """
    logger.info("=== Inizio fetch di tutti i feed ===")

    wm_articles, ai_articles = [], []

    for feed in WEB_MARKETING_FEEDS:
        wm_articles.extend(fetch_feed(feed))

    for feed in AI_FEEDS:
        ai_articles.extend(fetch_feed(feed))

    # Deduplicazione per URL
    def dedupe(articles: List[Dict]) -> List[Dict]:
        seen = set()
        result = []
        for a in articles:
            key = a["link"]
            if key not in seen:
                seen.add(key)
                result.append(a)
        return result

    result = {
        "web_marketing": dedupe(wm_articles),
        "ai":            dedupe(ai_articles),
    }

    # Rimuovi articoli già inviati
    sent_ids = set(_load_json(SENT_FILE, []))
    result["web_marketing"] = [a for a in result["web_marketing"] if a["id"] not in sent_ids]
    result["ai"]            = [a for a in result["ai"]            if a["id"] not in sent_ids]

    logger.info(
        f"Articoli nuovi → Web Marketing: {len(result['web_marketing'])}, "
        f"AI: {len(result['ai'])}"
    )

    # Salva in cache
    _save_json(CACHE_FILE, result)
    return result


def load_cached() -> Dict[str, List[Dict]]:
    """Carica articoli dalla cache locale."""
    return _load_json(CACHE_FILE, {"web_marketing": [], "ai": []})


def mark_as_sent(articles_wm: List[Dict], articles_ai: List[Dict]):
    """Segna gli articoli come già inviati per evitare duplicati."""
    sent_ids = set(_load_json(SENT_FILE, []))
    for a in articles_wm + articles_ai:
        sent_ids.add(a["id"])
    _save_json(SENT_FILE, list(sent_ids))
    logger.info(f"Marcati {len(articles_wm) + len(articles_ai)} articoli come inviati")
