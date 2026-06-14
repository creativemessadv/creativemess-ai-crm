# =====================================================================
#  fonte_prezzi.py - Lettura prezzi dall'API ufficiale pokemontcg.io
# ---------------------------------------------------------------------
#  Perché questa fonte: pokemontcg.io è un'API GRATUITA e LEGALE che
#  aggrega i prezzi di TCGplayer e Cardmarket. Usandola NON facciamo
#  scraping e quindi non violiamo i Terms of Service di nessuno.
#
#  Documentazione: https://docs.pokemontcg.io/
#  Chiave gratuita: https://dev.pokemontcg.io/
# =====================================================================

import requests

# Endpoint base dell'API (versione 2).
BASE_URL = "https://api.pokemontcg.io/v2"

# Timeout di sicurezza per ogni richiesta (secondi).
TIMEOUT = 30


def _intestazioni(api_key: str) -> dict:
    """Costruisce le intestazioni HTTP. La chiave è opzionale: se manca,
    l'API risponde comunque ma con limiti di richieste più bassi."""
    intestazioni = {"Accept": "application/json"}
    if api_key:
        intestazioni["X-Api-Key"] = api_key
    return intestazioni


def scarica_carte_di_set(set_id: str, api_key: str = "", max_carte: int = 250) -> list[dict]:
    """Scarica le carte di un set e ne estrae i prezzi.

    Restituisce una lista di dizionari "normalizzati", ognuno con:
      - dati anagrafici della carta (per la tabella 'carte')
      - una lista di scatti di prezzo (per la tabella 'prezzi')

    In caso di errore di rete restituisce una lista vuota (senza bloccare
    tutto il programma) e stampa un avviso.
    """
    risultati: list[dict] = []
    pagina = 1
    dimensione_pagina = 250  # massimo consentito dall'API per pagina

    while len(risultati) < max_carte:
        parametri = {
            "q": f"set.id:{set_id}",
            "page": pagina,
            "pageSize": dimensione_pagina,
            # Scarichiamo solo i campi che ci servono: più leggero e veloce.
            "select": "id,name,number,rarity,set,images,tcgplayer,cardmarket",
        }
        try:
            risposta = requests.get(
                f"{BASE_URL}/cards",
                headers=_intestazioni(api_key),
                params=parametri,
                timeout=TIMEOUT,
            )
            risposta.raise_for_status()
        except requests.RequestException as errore:
            print(f"  [ATTENZIONE] Errore scaricando il set {set_id}: {errore}")
            break

        dati = risposta.json().get("data", [])
        if not dati:
            break  # nessuna carta in questa pagina: abbiamo finito

        for carta_grezza in dati:
            risultati.append(_normalizza_carta(carta_grezza))

        # Se la pagina era incompleta, non ci sono altre pagine.
        if len(dati) < dimensione_pagina:
            break
        pagina += 1

    return risultati[:max_carte]


def _normalizza_carta(carta: dict) -> dict:
    """Trasforma la carta grezza dell'API in una struttura semplice e
    coerente con le nostre tabelle del database."""
    set_info = carta.get("set", {}) or {}
    immagini = carta.get("images", {}) or {}

    anagrafica = {
        "id": carta.get("id"),
        "nome": carta.get("name"),
        "set_id": set_info.get("id"),
        "set_nome": set_info.get("name"),
        "numero": carta.get("number"),
        "rarita": carta.get("rarity"),
        "immagine_url": immagini.get("large") or immagini.get("small"),
        "aggiornato_il": None,  # riempito sotto se disponibile
    }

    scatti_prezzo: list[dict] = []

    # --- Prezzi TCGplayer (in dollari) ------------------------------
    tcg = carta.get("tcgplayer") or {}
    anagrafica["aggiornato_il"] = tcg.get("updatedAt")
    for variante, valori in (tcg.get("prices") or {}).items():
        if not valori:
            continue
        scatti_prezzo.append({
            "fonte": "tcgplayer",
            "variante": variante,                      # es. "holofoil"
            "prezzo_market": valori.get("market"),
            "prezzo_basso": valori.get("low"),
            "prezzo_alto": valori.get("high"),
            "cm_avg1": None,
            "cm_avg7": None,
            "cm_avg30": None,
            "cm_trend": None,
        })

    # --- Prezzi Cardmarket (in euro) --------------------------------
    cm = carta.get("cardmarket") or {}
    prezzi_cm = cm.get("prices") or {}
    if prezzi_cm:
        if not anagrafica["aggiornato_il"]:
            anagrafica["aggiornato_il"] = cm.get("updatedAt")
        scatti_prezzo.append({
            "fonte": "cardmarket",
            "variante": "cardmarket",
            # Come prezzo di riferimento usiamo il "trendPrice" di Cardmarket.
            "prezzo_market": prezzi_cm.get("trendPrice"),
            "prezzo_basso": prezzi_cm.get("lowPrice"),
            "prezzo_alto": prezzi_cm.get("avg30"),
            "cm_avg1": prezzi_cm.get("avg1"),
            "cm_avg7": prezzi_cm.get("avg7"),
            "cm_avg30": prezzi_cm.get("avg30"),
            "cm_trend": prezzi_cm.get("trendPrice"),
        })

    anagrafica["_scatti_prezzo"] = scatti_prezzo
    return anagrafica
