"""
Agente Mailer: formatta e invia le due email HTML giornaliere.
"""

import smtplib
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List
from config import EMAIL_CONFIG

logger = logging.getLogger(__name__)

# ─── TEMPLATE HTML ───────────────────────────────────────────────────────────

_HTML_HEADER = """<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #0d0d0d;
      color: #e8e8e8;
      padding: 32px 16px;
    }}
    .container {{
      max-width: 680px;
      margin: 0 auto;
    }}
    .header {{
      background: linear-gradient(135deg, {gradient_start} 0%, {gradient_end} 100%);
      border-radius: 16px;
      padding: 32px;
      margin-bottom: 24px;
    }}
    .header .agency {{ color: rgba(255,255,255,0.7); font-size: 12px; font-weight: 600;
                       letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px; }}
    .header h1 {{ color: #fff; font-size: 26px; font-weight: 700; line-height: 1.3; }}
    .header .date {{ color: rgba(255,255,255,0.6); font-size: 13px; margin-top: 8px; }}
    .insight-box {{
      background: #1a1a1a;
      border-left: 4px solid {accent};
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 28px;
      font-size: 14px;
      color: #b0b0b0;
      line-height: 1.6;
    }}
    .insight-box strong {{ color: {accent}; }}
    .article {{
      background: #161616;
      border: 1px solid #2a2a2a;
      border-radius: 12px;
      padding: 20px 24px;
      margin-bottom: 16px;
      position: relative;
    }}
    .article:hover {{ border-color: {accent}; }}
    .rank {{
      display: inline-block;
      background: {accent};
      color: #000;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 20px;
      margin-bottom: 10px;
    }}
    .source {{
      display: inline-block;
      background: #222;
      color: #888;
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 20px;
      margin-left: 6px;
    }}
    .article h2 {{
      font-size: 16px;
      font-weight: 600;
      color: #f0f0f0;
      line-height: 1.4;
      margin-bottom: 10px;
    }}
    .article h2 a {{ color: inherit; text-decoration: none; }}
    .article h2 a:hover {{ color: {accent}; }}
    .why {{ font-size: 13px; color: #aaa; line-height: 1.6; margin-bottom: 10px; }}
    .takeaway {{
      background: #0f0f0f;
      border-radius: 6px;
      padding: 10px 14px;
      font-size: 12px;
      color: {accent};
      font-weight: 500;
    }}
    .takeaway span {{ color: #666; }}
    .published {{ font-size: 11px; color: #555; margin-top: 10px; }}
    .footer {{
      text-align: center;
      padding: 24px;
      font-size: 11px;
      color: #444;
      line-height: 1.8;
    }}
    .footer a {{ color: {accent}; text-decoration: none; }}
    .separator {{ height: 1px; background: #222; margin: 8px 0; }}
  </style>
</head>
<body>
<div class="container">
"""

_HTML_HEADER_BLOCK = """
  <div class="header">
    <div class="agency">Creative Mess ADV · Daily Intelligence</div>
    <h1>{emoji} {title}</h1>
    <div class="date">{date} · Curato da Claude AI</div>
  </div>
  <div class="insight-box">
    <strong>📊 Insight del giorno:</strong><br>{insight}
  </div>
"""

_HTML_ARTICLE = """
  <div class="article">
    <span class="rank">#{rank}</span>
    <span class="source">{source}</span>
    <h2><a href="{url}" target="_blank">{title}</a></h2>
    <div class="why">{why_important}</div>
    <div class="takeaway"><span>→ Key takeaway: </span>{key_takeaway}</div>
    <div class="published">Pubblicato: {published}</div>
  </div>
"""

_HTML_FOOTER = """
  <div class="footer">
    <div class="separator"></div>
    <br>
    <strong>Creative Mess ADV</strong> · AI-Powered News Digest<br>
    Email generata automaticamente ogni mattina alle 08:00<br>
    <a href="mailto:roberto@creativemessadv.it">roberto@creativemessadv.it</a>
  </div>
</div>
</body>
</html>"""

# ─── CONFIGURAZIONI VISIVE PER CATEGORIA ─────────────────────────────────────

_THEMES = {
    "web_marketing": {
        "gradient_start": "#7C3AED",
        "gradient_end":   "#2563EB",
        "accent":         "#A78BFA",
        "emoji":          "📢",
        "title":          "Web Marketing Digest",
    },
    "ai": {
        "gradient_start": "#059669",
        "gradient_end":   "#0891B2",
        "accent":         "#34D399",
        "emoji":          "🤖",
        "title":          "AI & Innovazione Digest",
    },
}


def _build_html(category: str, curated: Dict) -> str:
    theme = _THEMES[category]
    today = datetime.now().strftime("%A %d %B %Y").capitalize()
    subject = f"[{today}] {theme['title']}"

    html = _HTML_HEADER.format(
        subject=subject,
        gradient_start=theme["gradient_start"],
        gradient_end=theme["gradient_end"],
        accent=theme["accent"],
    )
    html += _HTML_HEADER_BLOCK.format(
        emoji=theme["emoji"],
        title=theme["title"],
        date=today,
        insight=curated.get("category_insight", ""),
    )

    for art in curated.get("selected", []):
        html += _HTML_ARTICLE.format(
            rank=art.get("rank", ""),
            source=art.get("source", ""),
            url=art.get("url", "#"),
            title=art.get("title", ""),
            why_important=art.get("why_important", ""),
            key_takeaway=art.get("key_takeaway", ""),
            published=art.get("published", ""),
        )

    html += _HTML_FOOTER
    return html, subject


def send_email(category: str, curated: Dict):
    """Invia l'email HTML per una categoria."""
    user     = os.environ.get("EMAIL_USER")
    password = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT", user)

    if not user or not password:
        logger.error("EMAIL_USER o EMAIL_PASSWORD non configurati. Imposta le variabili d'ambiente.")
        return False

    html_body, subject = _build_html(category, curated)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Creative Mess AI Digest <{user}>"
    msg["To"]      = recipient

    # Versione plain text di fallback
    plain = f"{subject}\n\n"
    for art in curated.get("selected", []):
        plain += f"#{art.get('rank')} {art.get('title')}\n{art.get('url')}\n{art.get('why_important')}\n\n"

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        logger.info(f"Invio email '{subject}' a {recipient}")
        with smtplib.SMTP(EMAIL_CONFIG["smtp_host"], EMAIL_CONFIG["smtp_port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [recipient], msg.as_bytes())
        logger.info("✅ Email inviata con successo")
        return True
    except Exception as e:
        logger.error(f"❌ Errore invio email: {e}")
        return False
