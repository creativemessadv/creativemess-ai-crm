# =====================================================================
#  analisi_trend.py - Logica per individuare le "carte calde"
# ---------------------------------------------------------------------
#  Idea: una carta è "calda" se il suo prezzo si sta muovendo
#  (di solito SALENDO) in modo significativo. Misuriamo il movimento in
#  due modi, in ordine di preferenza:
#
#    1. STORICO NOSTRO: confronto del prezzo di oggi con l'ultimo prezzo
#       che avevamo salvato per la stessa carta. Disponibile solo dal
#       secondo giorno in poi (serve almeno uno scatto precedente).
#
#    2. MOMENTUM CARDMARKET: se non abbiamo ancora storico, usiamo i dati
#       che Cardmarket fornisce già pronti: avg1 (media 1 giorno) contro
#       avg7 (media 7 giorni). Se avg1 > avg7 la carta sta salendo.
#
#  Restituiamo le prime N carte ordinate per variazione percentuale.
# =====================================================================

import database as db


def calcola_carte_calde(conn, data, prezzo_minimo, quante):
    """Analizza i prezzi del giorno 'data' e restituisce le carte calde.

    Ritorna una lista di dizionari pronti per essere salvati nella
    tabella 'carte_calde' e mostrati nel report.
    """
    candidate = []

    for riga in db.prezzi_del_giorno(conn, data):
        prezzo_oggi = riga["prezzo_market"]

        # Saltiamo carte senza prezzo o troppo economiche (rumore).
        if prezzo_oggi is None or prezzo_oggi < prezzo_minimo:
            continue

        variazione, motivo = _calcola_variazione(conn, riga, data)
        if variazione is None:
            continue

        candidate.append({
            "data": data,
            "carta_id": riga["carta_id"],
            # Il punteggio dà più peso alle carte di valore più alto:
            # un +20% su una carta da 80€ "scotta" più di un +20% su 2€.
            "punteggio": round(variazione * _peso_prezzo(prezzo_oggi), 2),
            "variazione_pct": round(variazione, 2),
            "motivo": motivo,
            # Campi extra solo per il report (non salvati a DB):
            "_nome": riga["nome"],
            "_set": riga["set_nome"],
            "_prezzo": prezzo_oggi,
            "_fonte": riga["fonte"],
        })

    # Ordiniamo per punteggio decrescente (le più "calde" in cima).
    candidate.sort(key=lambda c: c["punteggio"], reverse=True)
    return candidate[:quante]


def _calcola_variazione(conn, riga, data):
    """Calcola la variazione percentuale del prezzo per una carta.

    Restituisce una coppia (variazione_pct, testo_motivo). Se non è
    possibile calcolare nulla di sensato, restituisce (None, "").
    """
    prezzo_oggi = riga["prezzo_market"]

    # --- Metodo 1: confronto con il nostro storico -------------------
    precedente = db.prezzo_piu_recente_prima_di(
        conn, riga["carta_id"], riga["fonte"], riga["variante"], data
    )
    if precedente and precedente["prezzo_market"]:
        prezzo_prima = precedente["prezzo_market"]
        if prezzo_prima > 0:
            variazione = (prezzo_oggi - prezzo_prima) / prezzo_prima * 100
            motivo = (
                f"Prezzo passato da {prezzo_prima:.2f} a {prezzo_oggi:.2f} "
                f"(dal {precedente['data']})"
            )
            return variazione, motivo

    # --- Metodo 2: momentum Cardmarket (avg1 vs avg7) ----------------
    avg1, avg7 = riga["cm_avg1"], riga["cm_avg7"]
    if avg1 and avg7 and avg7 > 0:
        variazione = (avg1 - avg7) / avg7 * 100
        motivo = (
            f"Momentum Cardmarket: media 1g {avg1:.2f}€ vs media 7g {avg7:.2f}€"
        )
        return variazione, motivo

    # Nessun dato utile per giudicare il movimento.
    return None, ""


def _peso_prezzo(prezzo):
    """Fattore di peso che premia (leggermente) le carte di valore più alto.

    Usiamo una crescita logaritmica per non far dominare del tutto le
    carte costose: una carta da 5€ pesa ~1.5, una da 100€ pesa ~3.
    """
    from math import log10
    return 1 + log10(max(prezzo, 1))
