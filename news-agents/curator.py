"""
Agente Curator: usa Claude Opus con adaptive thinking per selezionare
e riassumere i migliori articoli del giorno.
"""

import anthropic
import json
import logging
from typing import List, Dict
from config import CLAUDE_MODEL, TOP_N_ARTICLES

logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

SYSTEM_PROMPT = """Sei un esperto analista di trend digitali per Creative Mess ADV,
una web agency italiana. Il tuo compito è selezionare le notizie più rilevanti,
innovative e azionabili per un team di professionisti del digital marketing e dell'AI.

LINGUA: Rispondi SEMPRE e SOLO in italiano. Traduci titoli, riassunti e analisi in italiano,
anche se gli articoli originali sono in inglese o altra lingua.

Criteri di selezione (in ordine di priorità):
1. Novità concreta e rilevante (non generic hype)
2. Impatto pratico per una web agency: nuovi strumenti, strategie, case study
3. Trend emergenti che possono dare vantaggio competitivo
4. Cambiamenti importanti negli algoritmi, piattaforme, modelli AI

Escludi: clickbait, notizie ripetitive, contenuti troppo generici o già noti."""


def _build_prompt(category: str, articles: List[Dict], top_n: int) -> str:
    category_label = "Web Marketing & SEO & Social Media" if category == "web_marketing" else "Intelligenza Artificiale & ML & LLM"

    articles_text = ""
    for i, a in enumerate(articles, 1):
        articles_text += f"""
---
{i}. [{a['source']}] {a['title']}
   URL: {a['link']}
   Data: {a['published'][:10]}
   Riassunto: {a['summary'] or 'N/D'}
"""

    return f"""Analizza questi {len(articles)} articoli recenti sulla categoria "{category_label}".

{articles_text}

Seleziona i {top_n} articoli più interessanti e impattanti per il team di Creative Mess ADV.

Rispondi ESCLUSIVAMENTE con un JSON valido, senza markdown, nel seguente formato:
{{
  "selected": [
    {{
      "rank": 1,
      "title": "TITOLO TRADOTTO IN ITALIANO (non lasciare in inglese)",
      "source": "nome fonte",
      "url": "url completo",
      "published": "YYYY-MM-DD",
      "why_important": "2-3 frasi in italiano che spiegano perché è rilevante per una web agency",
      "key_takeaway": "1 frase in italiano: cosa fare o tenere d'occhio concretamente"
    }}
  ],
  "category_insight": "1-2 frasi in italiano sul trend generale emergente da questi articoli oggi"
}}"""


def curate(category: str, articles: List[Dict]) -> Dict:
    """
    Usa Claude per selezionare e arricchire i migliori articoli.
    Ritorna un dict con 'selected' e 'category_insight'.
    """
    if not articles:
        logger.warning(f"Nessun articolo da curare per '{category}'")
        return {"selected": [], "category_insight": "Nessuna notizia rilevante trovata oggi."}

    top_n = min(TOP_N_ARTICLES, len(articles))
    prompt = _build_prompt(category, articles, top_n)

    logger.info(f"Chiamata Claude per curazione '{category}' ({len(articles)} articoli → top {top_n})")

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Estrai testo dalla risposta (salta eventuali thinking blocks)
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        # Pulisci eventuali backtick markdown
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)
        logger.info(f"Curazione completata: {len(result.get('selected', []))} articoli selezionati")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Errore parsing JSON da Claude: {e}\nRisposta: {text[:200]}")
        return _fallback_selection(articles, top_n)

    except Exception as e:
        logger.error(f"Errore chiamata Claude: {e}")
        return _fallback_selection(articles, top_n)


def _fallback_selection(articles: List[Dict], top_n: int) -> Dict:
    """Fallback: seleziona i primi N articoli senza AI se Claude fallisce."""
    selected = []
    for i, a in enumerate(articles[:top_n], 1):
        selected.append({
            "rank": i,
            "title": a["title"],
            "source": a["source"],
            "url": a["link"],
            "published": a["published"][:10],
            "why_important": "Articolo rilevante dalla fonte selezionata.",
            "key_takeaway": "Leggi l'articolo per maggiori dettagli.",
        })
    return {
        "selected": selected,
        "category_insight": "Digest automatico (curazione AI non disponibile).",
    }
