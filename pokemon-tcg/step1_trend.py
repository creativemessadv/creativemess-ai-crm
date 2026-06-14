#!/usr/bin/env python3
# =====================================================================
#  step1_trend.py - Script principale dello STEP 1 (Modulo Trend)
# ---------------------------------------------------------------------
#  Questo è il file che lanci ogni giorno. In sequenza:
#    1. apre/crea il database SQLite
#    2. scarica i prezzi dei set monitorati (fonte: pokemontcg.io)
#    3. scarica l'interesse Google Trends per le parole chiave
#    4. analizza i dati e individua le 3-5 "carte calde" del giorno
#    5. salva tutto a database e scrive un report markdown leggibile
#
#  USO:
#    cd pokemon-tcg
#    python3 step1_trend.py
# =====================================================================

from datetime import date
from pathlib import Path

import config
import database as db
import fonte_prezzi
import fonte_trends
import analisi_trend


def main() -> None:
    oggi = date.today().isoformat()
    print(f"=== Modulo Trend Pokémon TCG - {oggi} ===\n")

    # --- 1. Database -------------------------------------------------
    conn = db.connetti(config.DB_PATH)
    db.inizializza_schema(conn)
    print(f"Database pronto: {config.DB_PATH}")

    # --- 2. Prezzi (pokemontcg.io) -----------------------------------
    print("\n[1/3] Scarico i prezzi dei set monitorati...")
    totale_carte = 0
    totale_prezzi = 0
    for set_id in config.SET_DA_MONITORARE:
        carte = fonte_prezzi.scarica_carte_di_set(
            set_id, config.POKEMONTCG_API_KEY, config.MAX_CARTE_PER_SET
        )
        for carta in carte:
            scatti = carta.pop("_scatti_prezzo", [])
            db.salva_carta(conn, carta)
            totale_carte += 1
            for scatto in scatti:
                scatto["carta_id"] = carta["id"]
                scatto["data"] = oggi
                db.salva_prezzo(conn, scatto)
                totale_prezzi += 1
        print(f"  - {set_id}: {len(carte)} carte")
    conn.commit()
    print(f"  Totale: {totale_carte} carte, {totale_prezzi} scatti di prezzo salvati.")

    # --- 3. Google Trends --------------------------------------------
    print("\n[2/3] Scarico Google Trends...")
    interesse = fonte_trends.scarica_interesse(
        config.KEYWORD_TRENDS, config.TRENDS_PAESE, config.TRENDS_PERIODO
    )
    for keyword, valore in interesse.items():
        db.salva_trend(conn, keyword, oggi, valore)
        print(f"  - {keyword}: {valore}/100")
    conn.commit()
    if not interesse:
        print("  (nessun dato Trends questa volta - vedi avvisi sopra)")

    # --- 4. Analisi carte calde --------------------------------------
    print("\n[3/3] Analizzo le carte calde...")
    calde = analisi_trend.calcola_carte_calde(
        conn, oggi, config.PREZZO_MINIMO_ANALISI, config.NUMERO_CARTE_CALDE
    )
    for calda in calde:
        # Salviamo solo i campi "ufficiali" (quelli con _ sono per il report).
        db.salva_carta_calda(conn, {
            "data": calda["data"],
            "carta_id": calda["carta_id"],
            "punteggio": calda["punteggio"],
            "variazione_pct": calda["variazione_pct"],
            "motivo": calda["motivo"],
        })
    conn.commit()

    if calde:
        for i, c in enumerate(calde, 1):
            print(f"  {i}. {c['_nome']} ({c['_set']}) "
                  f"{c['variazione_pct']:+.1f}% - {c['_prezzo']:.2f} [{c['_fonte']}]")
    else:
        print("  Nessuna carta calda rilevata oggi.")
        print("  Suggerimento: al primo avvio non c'è storico; rilancia domani")
        print("  per il confronto giorno-su-giorno, oppure aspettati segnali")
        print("  solo dal momentum Cardmarket.")

    # --- 5. Report markdown ------------------------------------------
    percorso_report = scrivi_report(oggi, calde, interesse)
    print(f"\nReport salvato in: {percorso_report}")
    print("\nFatto. Rilancia lo script ogni giorno per costruire lo storico.")
    conn.close()


def scrivi_report(oggi: str, calde: list, interesse: dict) -> Path:
    """Scrive un report giornaliero in markdown nella cartella 'report/'."""
    config.REPORT_DIR.mkdir(exist_ok=True)
    percorso = config.REPORT_DIR / f"trend_{oggi}.md"

    righe = [f"# Report Trend Pokémon TCG — {oggi}\n"]

    righe.append("## 🔥 Carte calde del giorno\n")
    if calde:
        righe.append("| # | Carta | Set | Variazione | Prezzo | Fonte | Motivo |")
        righe.append("|---|-------|-----|-----------|--------|-------|--------|")
        for i, c in enumerate(calde, 1):
            righe.append(
                f"| {i} | {c['_nome']} | {c['_set']} | "
                f"{c['variazione_pct']:+.1f}% | {c['_prezzo']:.2f} | "
                f"{c['_fonte']} | {c['motivo']} |"
            )
    else:
        righe.append("_Nessuna carta calda rilevata oggi "
                     "(serve almeno un giorno di storico per i confronti)._")

    righe.append("\n## 📈 Google Trends\n")
    if interesse:
        righe.append("| Parola chiave | Interesse (0-100) |")
        righe.append("|---------------|-------------------|")
        for keyword, valore in sorted(interesse.items(), key=lambda x: -x[1]):
            righe.append(f"| {keyword} | {valore} |")
    else:
        righe.append("_Dati Google Trends non disponibili questa volta._")

    righe.append("\n---")
    righe.append("_Generato automaticamente dal Modulo Trend (Step 1). "
                 "Le carte calde diventano lo spunto per lo Step 2 (caption/script)._")

    percorso.write_text("\n".join(righe), encoding="utf-8")
    return percorso


if __name__ == "__main__":
    main()
